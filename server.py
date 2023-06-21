from flask import Flask, request
import json
import uuid
import queue
from threading import Thread, Semaphore

import sys
import os
import fnmatch

from dateutil.parser import parse
from datetime import timezone
from datetime import datetime

import zipfile

app = Flask(__name__)

task_queue = queue.Queue() # очередь задач
completed_tasks = {}       # словарь результатов

s = Semaphore(1)           # семафор, для контроля доступа к словарю из разных потоков
                           # т.к. очередь - потокобезопасный ресурс, а словарь - нет

def compare(val, fval, op):
    return ((op == "eq" and fval == val) or     # равно
           (op == "gt" and fval > val) or       # больше
           (op == "lt" and fval < val) or       # меньше
           (op == "ge" and fval >= val) or      # больше или равно
           (op == "le" and fval <= val))        # меньше или равно
           
           
def check_filters(filename, fname, filters):
    stat_info = os.stat(fname) # получаем системную информацию о файле
    if "file_mask" in filters.keys():
        if not fnmatch.fnmatch(filename, filters["file_mask"]):
            return False
    if "size" in filters.keys():
        size = filters["size"]["value"]
        op = filters["size"]["operator"]
        fsize = stat_info.st_size
        if not compare(size, fsize, op):
            return False
    if "creation_time" in filters.keys():
        time = filters["creation_time"]["value"]
        op = filters["creation_time"]["operator"]
        if hasattr(stat_info, "st_birthtime"):
            # это поле есть не во всех Unix системах, но является более точным
            ftime = stat_info.st_birthtime
        else:
            # есть в большинстве Unix системах, 
            # но отражает время последнего изменения индексного дескриптора
            ftime = stat_info.st_ctime
        time = parse(time)
        ftime = datetime.fromtimestamp(ftime, timezone.utc)
        if not compare(time, ftime, op):
            return False
    if "text" in filters.keys():
        with open(fname, 'rb') as f:
            if filters["text"].encode('utf-8') not in f.read():
                return False
    return True
    
    
def zip_filters(fname, filters):
    ans = []
    stat_info = os.stat(fname) # получаем системную информацию о файле
    
    # в задании не говорилось, можно ли разархивировать zip-файл, но иначе
    # нельзя получить системную информацию о дате создания файлов внутри архива
    # в информации, получаемой без распаковки архива, содержится только дата
    # последней модификации файла
    # предположив, что распаковка нежелательна, я приняла решение применять фильтр
    # к дате создания самого архива
    if "creation_time" in filters.keys():
        time = filters["creation_time"]["value"]
        op = filters["creation_time"]["operator"]
        if hasattr(stat_info, "st_birthtime"):
            # это поле есть не во всех Unix системах, но является более точным
            ftime = stat_info.st_birthtime
        else:
            # есть в большинстве Unix систем, 
            # но отражает время последнего изменения индексного дескриптора
            ftime = stat_info.st_ctime
        time = parse(time)
        ftime = datetime.fromtimestamp(ftime, timezone.utc)
        if not compare(time, ftime, op):
            return ans
    with zipfile.ZipFile(fname, mode='r') as arch:
        for info in arch.infolist():
            if "file_mask" in filters.keys():
                if not fnmatch.fnmatch(info.filename, filters["file_mask"]):
                    continue
            if "text" in filters.keys():
                if filters["text"].encode('utf-8') not in arch.read(info.filename):
                    continue
            if "size" in filters.keys():
                size = filters["size"]["value"]
                op = filters["size"]["operator"]
                fsize = info.file_size
                if not compare(size, fsize, op):
                    continue
            ans.append(fname + '/' + info.filename)
    return ans


def file_finder(top_name):
    while True:
        if task_queue.empty(): #если очередь задач пуста, то функция "простаивает"
            continue
        task = task_queue.get()
        ans = []
        search_id = task[0]
        filters = task[1]
        for dirpath, dirnames, filenames in os.walk(top_name): # получаем все файлы и файлы из всех директорий из "верхней"
            for filename in filenames:
                fname = os.path.join(dirpath, filename)
                if zipfile.is_zipfile(fname):
                    zip_ans = zip_filters(fname, filters)
                    ans.extend(zip_ans)
                elif check_filters(filename, fname, filters):
                    ans.append(fname)
        s.acquire()
        completed_tasks[str(search_id)] = {'finished': True, 'paths': ans} # добавляем в решённые задачи результат
        s.release()


@app.route('/search', methods = ['POST'])
def search():
    # в задании не указан тип данных, но тело запроса имеет формат json
    # эта строка будет обрабатывать контент типа application/json и text/plain
    req_body = json.loads(request.data)
    search_id = uuid.uuid4()
    task_queue.put((search_id, req_body))
    return json.dumps({'search_id': str(search_id)})


@app.route('/searches/<string:search_id>', methods = ['GET'])
def get_result(search_id):
    s.acquire()
    if search_id not in completed_tasks.keys():
        ans = {"finished": False}
    else:
        ans = completed_tasks[search_id]
    s.release()
    return json.dumps(ans)


if __name__ == "__main__":
    directory = sys.argv[1]
    app = Thread(target=app.run, daemon=True)
    app.start()
    try:
        file_finder(directory)
    except KeyboardInterrupt:
        pass
