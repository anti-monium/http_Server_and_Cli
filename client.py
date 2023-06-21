import http.client
import cmd
import threading
        

class Client_cmd(cmd.Cmd):
    intro = ('Type help to see available commands.'
        + '\nComplete key is TAB.'
        + '\nThe program maintains a history of commands, ' 
        + 'access to it is provided by the up and down arrows.')
    
    prompt = '>>>> '
    
    def do_GET(self, arg):
        '''
        Sends GET request to get information about search
        Syntax: GET /searches/<search_id>
        Returns information about a search request by id
        '''
        global conn, conn_flag
        conn.request("GET", arg)
        response = conn.getresponse()
        print(f'{response.status} {response.reason}\n{response.read().decode()}')
        
    def complete_GET(self, prefix, line, start, end):
        line = line.split()
        if line[0] == 'GET' and len(line) == 1:
            return ['/searches/']
        
    def do_POST(self, arg):
        '''
        Sends POST request to search for files by filters from file
        The program itself will ask you to enter a file name
        Syntax: POST /search
        Returns search_id to use it in GET request
        '''
        global conn, conn_flag
        headers = {'Content-type': 'text/plain'}
        f_json = open(input('Print JSON file name: '), 'r')
        body = f_json.read()
        f_json.close()
        conn.request("POST", arg, body, headers)
        response = conn.getresponse()
        print(f'{response.status} {response.reason}\n{response.read().decode()}')
        
    def complete_POST(self, prefix, line, start, end):
        line = line.split()
        if line[0] == 'POST' and len(line) == 1:
            return ['/search']

    def do_quit(self, arg):
        '''
        Closes the connection to the server and terminates the client
        '''
        global conn
        conn.close()
        return True
        

conn = http.client.HTTPConnection("localhost", 5000)
cmdline = Client_cmd(completekey='tab')
cmdline.cmdloop()
