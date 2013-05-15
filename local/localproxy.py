#!/usr/bin/env python
import sys
import socket

import tornado.httpserver
import tornado.ioloop
import tornado.iostream
import tornado.web
import tornado.httpclient
import tornado.options

from ConfigParser import SafeConfigParser
import myconfigparser
from tornado.options import define, options
define("port", default=8080)
define("CONFIG_FILE", default="config.ini")
parser = SafeConfigParser()
parser.read(options.CONFIG_FILE)
REMOTE_IP = parser.get('Server', 'ip')


class ProxyHandler(tornado.web.RequestHandler):

    @tornado.web.asynchronous
    def get(self):

        def handle_response(response):
            if response.error and not isinstance(response.error,
                                                 tornado.httpclient.HTTPError):
                self.set_status(500)
                self.write('Internal server error:\n' + str(response.error))
                self.finish()
            else:
                self.set_status(response.code)
                for header in ('Date', 'Cache-Control', 'Server',
                               'Content-Type', 'Location'):
                    v = response.headers.get(header)
                    if v:
                        self.set_header(header, v)
                if response.body:
                    self.write(response.body)
                self.finish()

        req = tornado.httpclient.HTTPRequest(url=self.request.uri,
                                             method=self.request.method, body=self.request.body,
                                             headers=self.request.headers, follow_redirects=False,
                                             allow_nonstandard_methods=True)
        print '##############################\n'
        print self.request
        print '##############################\n'

        client = tornado.httpclient.AsyncHTTPClient()
        try:
            client.fetch(req, handle_response)
        except tornado.httpclient.HTTPError as e:
            if hasattr(e, 'response') and e.response:
                handle_response(e.response)
            else:
                self.set_status(500)
                self.write('Internal server error:\n' + str(e))
                self.finish()

    @tornado.web.asynchronous
    def post(self):
        return self.get()

    @tornado.web.asynchronous
    def connect(self):
        host, port = self.request.uri.split(':')
        client = self.request.connection.stream

        def read_from_client(data):
            upstream.write(data)

        def read_from_upstream(data):
            client.write(data)

        def client_close(data=None):
            if upstream.closed():
                return
            if data:
                upstream.write(data)
            upstream.close()

        def upstream_close(data=None):
            if client.closed():
                return
            if data:
                client.write(data)
            client.close()

        def start_tunnel():
            client.read_until_close(client_close, read_from_client)
            upstream.read_until_close(upstream_close, read_from_upstream)
            client.write(b'HTTP/1.0 200 Connection established\r\n\r\n')

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        upstream = tornado.iostream.IOStream(s)
        upstream.connect((host, int(port)), start_tunnel)


class Applicaion(tornado.web.Application):

    def __init__(self):
        handlers = [(r".*", ProxyHandler)]
        tornado.web.Application.__init__(self, handlers, debug=False)

if __name__ == '__main__':
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Applicaion())
    http_server.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()
