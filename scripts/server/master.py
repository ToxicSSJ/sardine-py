from bottle import Bottle, HTTPResponse, BaseRequest, request, response, route, run, template, static_file
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib3.exceptions import NewConnectionError

from flask import Flask
from tinydb import TinyDB, Query

import os
import time
import json
import base64
import logging
import requests
import binascii
import threading

BaseRequest.MEMFILE_MAX = 10000000 # (or whatever you want)

class Server:

    def __init__(self, host, port, config, logger):
        self._host = host
        self._port = port
        self._servers = set()
        self._app = Bottle()
        self._route()

        self.logger = logger
        self.config = config

        threading.Thread(target=self._repeatstatus, args=[], daemon=True).start()

    def _route(self):
        self._app.route('/ping', method="GET", callback=self._index)
        self._app.route('/register/<server>', method="GET", callback=self._register)
        self._app.route('/unregister/<server>', method="GET", callback=self._unregister)
        self._app.route('/find/<hash>', method="GET", callback=self._find)
        self._app.route('/space/<bytes>', method="GET", callback=self._space)

    def start(self):
        self._app.run(host=self._host, port=self._port)

    def _repeatstatus(self):

        time.sleep(10)
        self.logger.info('Checking status of the clients...')

        copy = self._servers.copy()

        for server in copy:
            response = self._serverGetRequest(server, '/ping')
            if response == None or response.status_code != 200:
                self._servers.remove(server)

        self.logger.info('Online clients: ' + json.dumps(list(self._servers)))
        self._repeatstatus()

    def _index(self):
        return 'Server master running... (200 OK)!'

    def _register(self, server):

        self.logger.info('Registering server: ' + server)

        self._servers.add(server)
        return self._message(200, 'REGISTERED')

    def _unregister(self, server):

        self.logger.info('Unregistering server: ' + server)

        self._servers.remove(server)
        return self._message(200, 'UNREGISTERED')

    def _space(self, bytes):

        self.logger.info('Finding clients with (' + bytes + ') space...')
        copy = self._servers.copy()

        result = []

        for server in copy:
            response = self._serverGetRequest(server, '/space/' + bytes)
            if response == None or response.status_code != 200:
                self._servers.remove(server)
            else:
                sresponse = response.json()
                if 'response' in sresponse:
                    if 'available' in sresponse['response']:
                        available = bool(sresponse['response']['available'])
                        if available == True:
                            result.append({'server': server, 'available': available, 'current': int(sresponse['response']['current']), 'max': int(sresponse['response']['max'])})

        return self._response(200, result)

    def _find(self, hash):

        self.logger.info('Finding (' + hash + ') clients...')
        copy = self._servers.copy()

        result = []

        for server in copy:
            response = self._serverGetRequest(server, '/list')
            if response == None or response.status_code != 200:
                self._servers.remove(server)
            else:
                sresponse = response.json()
                if 'response' in sresponse:
                    if 'files' in sresponse['response']:
                        files = sresponse['response']['files']
                        for file in files:
                            if file['hash'] == hash:
                                file['server'] = server
                                result.append(file)

        return self._response(200, result)

    def _serverGetRequest(self, url, route):

        try:
            url = 'http://' + url + route
            return requests.get(url=url)
        except requests.exceptions.RequestException as e:
            return None

    def _response(self, code, json):
        return HTTPResponse(status=code, body={'code': code, 'response': json}, headers={'Access-Control-Allow-Origin': '*'})

    def _message(self, code, message):
        return HTTPResponse(status=code, body={'code': code, 'message': message}, headers={'Access-Control-Allow-Origin': '*'})

def run_master(hostname, port, config, logger):
    threading.Thread(target=th, args=[hostname, port, config, logger,], daemon=True).start()

def th(hostname, port, config, logger):
    server = Server(host=hostname, port=port, config=config, logger=logger)
    server.start()