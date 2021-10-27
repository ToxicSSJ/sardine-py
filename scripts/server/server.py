from http.server import BaseHTTPRequestHandler, HTTPServer
from py_essentials import hashing as hs
from tinydb import TinyDB, Query
from flask import Flask, app, request, jsonify

import os
import json
import time
import base64
import random
import secrets
import logging
import requests
import binascii
import threading
import http.client

class Server:

    def __init__(self, host, port, config, logger):
        self._host = host
        self._port = port
        self._app = Flask(__name__)

        self.logger = logger
        self.config = config

        self.db = TinyDB('../database/client.json')
        self.files = self.db.table('files')
        self.transactions = self.db.table('transactions')

        self._route()
        self._master()

    def _master(self):
        threading.Thread(target=self._repeatmaster, args=[], daemon=True).start()

    def _repeatmaster(self):
        self._masterRequest('/register/' + self._host + ':' + self._port)
        self.logger.info('Registering master...')
        time.sleep(10)
        self._repeatmaster()

    def _route(self):

        self._app.add_url_rule('/ping', view_func=self._ping, methods=["GET"])

        self._app.add_url_rule('/remove/<filename>', view_func=self._remove, methods=["DELETE"])
        self._app.add_url_rule('/list', view_func=self._list, methods=["GET"])
        self._app.add_url_rule('/space/<size>', view_func=self._space, methods=["GET"])

        self._app.add_url_rule('/download/<hash>', view_func=self._downloadsingle, methods=["GET"])
        self._app.add_url_rule('/chunks/download/<hash>/<index>', view_func=self._downloadchunk, methods=["GET"])

        self._app.add_url_rule('/upload', view_func=self._uploadsingle, methods=["PUT"])
        self._app.add_url_rule('/chunks/upload', view_func=self._uploadchunk, methods=["PUT"])

        self._app.add_url_rule('/master/find/<hash>', view_func=self._findmaster, methods=["GET"])
        self._app.add_url_rule('/master/space/<bytes>', view_func=self._spacemaster, methods=["GET"])
        self._app.add_url_rule('/master/chunks/upload', view_func=self._uploadchunkmaster, methods=["PUT"])
        self._app.add_url_rule('/master/single/upload', view_func=self._uploadsinglemaster, methods=["PUT"])
        self._app.add_url_rule('/master/chunks/download/<hash>', view_func=self._downloadchunkmaster, methods=["GET"])
        self._app.add_url_rule('/master/single/download/<hash>', view_func=self._downloadsinglemaster, methods=["GET"])

    def start(self):
        self._app.run(host=self._host, port=self._port, threaded=True)

    def _ping(self):
        return 'Server running... (200 OK)!'

    def _list(self):

        results = self.files.all()
        return self._response(200, { 'files': results })

    def _spacemaster(self, bytes):

        self.logger.info('Finding space of (' + bytes + ') in master...')
        response = self._masterRequest('/space/' + bytes)

        if response.status_code != 200:
            self.logger.error('Master status code is: ' + str(response.status_code))
            return self._response(500, 'MASTER IS OFFLINE')

        response = response.json()
        return response

    def _space(self, size):

        files = [f for f in os.listdir("../files/") if os.path.isfile(os.path.join("../files/", f))]

        size = int(size)
        current = 0
        max = int(self.config['bottle']['allocation'])
        available = True

        for file in files:
            current += os.path.getsize("../files/" + file)

        if (current + size) >= max:
            available = False

        return self._response(200, { 'available': available, 'current': current, 'max': max })

    def _save(self):

        body = request.json

        if not 'name' in body:
            return self._message(400, 'PARAMETER NAME IS REQUIRED')

        if not 'data' in body:
            return self._message(400, 'DATA IS REQUIRED')

        name = body['name']
        data = body['data']

        try:

            id = secrets.token_hex(nbytes=16)
            b64data = base64.b64decode(data)

            if os.path.isfile("../files/" + name):
                return self._message(409, 'FILE ALREADY EXISTS')

            f = open("../files/" + name, "wb")
            f.write(b64data)
            f.close()

            hash = hs.fileChecksum("../files/" + name, "sha256")
            print(hash)

        except binascii.Error:
            return self._message(400, 'INVALID PAYLOAD')

        return self._message(200, 'UPLOADED')

    def _findmaster(self, hash):

        self.logger.info('Finding hash (' + hash + ') in master...')
        response = self._masterRequest('/find/' + hash)

        if response.status_code != 200:
            self.logger.error('Master status code is: ' + str(response.status_code))
            return self._response(500, 'MASTER IS OFFLINE')

        response = response.json()
        return response

    def _downloadsinglemaster(self, hash):

        self.logger.info('Finding hash (' + hash + ') in master...')
        response = self._masterRequest('/find/' + hash)

        if response.status_code != 200:
            self.logger.error('Master status code is: ' + str(response.status_code))
            return self._response(500, 'MASTER IS OFFLINE')

        response = response.json()

        if not 'response' in response:
            return self._response(404, 'FILE NOT FOUND')

        files = response['response']
        candidates = []

        for file in files:
            if file['type'] == 'one':
                candidates.append(file)

        if len(candidates) == 0:
            return self._response(404, 'FILE NOT FOUND')

        return self._downloadsinglemastercandidate(hash, candidates)

    def _downloadsinglemastercandidate(self, hash, candidates):

        if len(candidates) == 0:
            return self._response(400, 'ALL MIRRORS ARE UNAVIALABLE')

        current = candidates[0]
        candidates.remove(current)

        response = self._serverGetRequest(current['server'], '/download/' + hash)

        if response.status_code != 200:
            return self._downloadsinglemastercandidate(self, hash, candidates)

        json = response.json()['response']
        return self._response(200, { 'filename': json['filename'], 'data': json['data'] })

    def _downloadsingle(self, hash):

        File = Query()
        files = self.files.search(File.hash == hash)

        if len(files) == 0:
            return self._message(400, 'FILE NOT EXISTS')

        file = files[0]

        if file['type'] == 'chunk':
            return self._message(400, 'USE CHUNK DOWNLOADER INSTEAD')

        if not os.path.isfile("../files/" + file['filename']):
            return self._message(400, 'FILE NOT EXISTS')

        lfile = open("../files/" + file['filename'], "rb")
        lread = lfile.read()

        b64 = str(base64.b64encode(lread), 'utf-8')

        return self._response(200, { 'filename': file['uploadname'], 'data': b64 })

    def _downloadchunkmaster(self, hash):

        self.logger.info('Finding hash (' + hash + ') in master...')
        response = self._masterRequest('/find/' + hash)

        if response.status_code != 200:
            self.logger.error('Master status code is: ' + str(response.status_code))
            return self._response(500, 'MASTER IS OFFLINE')

        response = response.json()

        if not 'response' in response:
            return self._response(404, 'FILE NOT FOUND')

        files = response['response']
        candidates = []

        for file in files:
            if file['type'] == 'chunk':
                candidates.append(file)

        if len(candidates) == 0:
            return self._response(404, 'FILE NOT FOUND')

        return self._downloadchunkmastercandidate(hash=hash, candidates=candidates)

    def _downloadchunkmastercandidate(self, hash, index=None, max=None, candidates=list(), total=None):

        self.logger.info('Checking candidates for hash (' + hash + ')...')

        if len(candidates) == 0:
            self.logger.info('No more candidates available, aborting chunk download for hash (' + hash + ')...')
            return self._response(400, 'ALL MIRRORS ARE UNAVIALABLE')

        current = None

        if max == None or index == None:
            for candidate in candidates:
                index = 1
                max = candidate['partition']['max']
                self.logger.info('Set start point for index=(' + str(index) + ') and max=(' + str(max) + ')...')
                break

        self.logger.info('Finding candidate for current index...')
        found = False

        for candidate in candidates.copy():
            self.logger.info(str(candidate))
            if index == candidate['partition']['index']:
                found = True
                current = candidate
                self.logger.info('Found candidate for index=(' + str(index) + ')!')
                break

        if found == False or current == None:
            return self._downloadchunkmastercandidate(hash=hash, index=None, max=None, candidates=candidates, total=total)

        candidates.remove(current)

        self.logger.info('Downloading part (' + str(index) + ' of  ' + str(max) + ') from candidate (' + current['server'] + ')...')
        response = self._serverGetRequest(current['server'], '/chunks/download/' + hash + '/' + str(index))

        self.logger.info('Response code: ' + str(response.status_code))

        if response.status_code != 200:
            time.sleep(1000)
            return self._downloadchunkmastercandidate(hash=hash, index=index, max=max, candidates=candidates, total=total)

        json = response.json()['response']

        if total == None:
            total = json['data']
        else:
            total += json['data']

        if index == max:
            return self._response(200, { 'filename': json['filename'], 'data': total })

        return self._downloadchunkmastercandidate(hash=hash, index=index + 1, max=max, candidates=candidates, total=total)

    def _downloadchunk(self, hash, index):

        File = Query()
        results = self.files.search(File.fragment({'hash': hash, 'type': 'chunk'}))

        index = int(index)

        for result in results:
            if result['partition']['index'] == index:

                self.logger.info('Chunk found for (' + hash + ') index (' + str(index) + ')')

                lfile = open("../files/" + result['filename'], "rb")
                lread = str(lfile.read(), 'utf-8')

                return self._response(200, { 'filename': result['uploadname'], 'hash': hash, 'index': index, 'max': result['partition']['max'], 'data': lread})
                

        #b64 = str(base64.b64encode(lread), 'utf-8')

        return self._response(200, "")

    def _uploadchunk(self):

        body = request.json

        if not 'name' in body:
            return self._message(400, 'PARAMETER NAME IS REQUIRED')

        if not 'data' in body:
            return self._message(400, 'DATA IS REQUIRED')

        if not 'partition' in body:
            return self._message(400, 'PARTITION DATA IS REQUIRED')

        if not 'checksum' in body['partition']:
            return self._message(400, 'PARTITION CHEKSUM IS REQUIRED')

        if not 'index' in body['partition']:
            return self._message(400, 'PARTITION INDEX IS REQUIRED')

        if not 'max' in body['partition']:
            return self._message(400, 'PARTITION MAX IS REQUIRED')

        name = body['name']
        data = body['data']

        original_checksum = body['partition']['checksum'] 
        chunk_index = body['partition']['index']
        chunk_max = body['partition']['max']

        if original_checksum == "":
            return self._message(400, 'BAD ORIGINAL CHECKSUM')

        if len(original_checksum) <= 5:
            return self._message(400, 'BAD ORIGINAL CHECKSUM')

        try:

            temp = secrets.token_hex(nbytes=16)

            if os.path.isfile("../files/" + temp):
                return self._message(409, 'FILE ALREADY EXISTS')

            f = open("../files/" + temp, "w")
            f.write(data)
            f.close()

            hash = hs.fileChecksum("../files/" + temp, "sha256")

            File = Query()
            results = self.files.search(File.fragment({'hash': original_checksum, 'type': 'chunk'}))

            '''if len(results) == 0:

                self.files.insert(
                    {
                        'type': 'chunk',
                        'hash': original_checksum,
                        'uploadname': name,
                        'filename': temp,
                        'partition': {
                            'checksum': hash,
                            'index': chunk_index,
                            'max': chunk_max
                        }
                    })
                self.logger.info('Uploaded new chunk to (' + original_checksum + ')[' + name + '] into this node!')

                return self._message(200, 'CHUNK UPLOADED')

            else:

                self.files.update({'type': 'chunk', 'hash': original_checksum, 'uploadname': name, 'filename': temp}, (File.hash == original_checksum) & (File.partition.checksum == hash) & (File.partition.index == chunk_index))
                self.logger.info('Replacing file (' + original_checksum + ')[' + name + '] into this node!')

                return self._message(200, 'UPLOADED')'''

            self.files.insert(
                {
                    'type': 'chunk',
                    'hash': original_checksum,
                    'uploadname': name,
                    'filename': temp,
                    'partition': {
                        'checksum': hash,
                        'index': chunk_index,
                        'max': chunk_max
                    }
                })
            self.logger.info('Uploaded new chunk to (' + original_checksum + ')[' + name + '] into this node!')

            return self._message(200, 'CHUNK UPLOADED')

        except binascii.Error:
            return self._message(400, 'INVALID PAYLOAD')

    def _uploadchunkmaster(self):

        body = request.json

        if not 'name' in body:
            return self._message(400, 'PARAMETER NAME IS REQUIRED')

        if not 'data' in body:
            return self._message(400, 'DATA IS REQUIRED')

        name = body['name']
        data = body['data']

        temp = secrets.token_hex(nbytes=16)
        b64data = base64.b64decode(data)

        if os.path.isfile("../files/" + temp):
            return self._message(409, 'FILE ALREADY EXISTS')

        f = open("../files/" + temp, "wb")
        f.write(b64data)
        f.close()

        hash = hs.fileChecksum("../files/" + temp, "sha256")
        size = os.path.getsize("../files/" + temp)

        self.logger.info('File total size of (' + str(size) + ' bytes) splitting...')

        counter = 0
        chunk = ''
        chunks = []

        for c in data:
            chunk = chunk + c
            counter += 1
            if counter == 1000000:
                chunks.append(chunk)
                chunk = ''
                counter = 0

        if counter > 0:
            chunks.append(chunk)
            chunk = ''
            counter = 0

        self.logger.info('File splitted in (' + str(len(chunks)) + ' chunks)!')
        candidates = []

        for ch in chunks:
            chsize = len(ch.encode('utf-8'))
            self.logger.info('Finding space of (' + str(chsize) + ' bytes) in master...')
            response = self._masterRequest('/space/' + str(chsize))
            if response.status_code != 200:
                self.logger.error('Master status code is: ' + str(response.status_code))
                return self._response(500, 'MASTER IS OFFLINE')
            response = response.json()
            if not 'response' in response:
                return self._response(404, 'SPACE NOT FOUND FOR CHUNK')
            spaces = response['response']
            for space in spaces:
                if space['server'] != (self._host + ':' + self._port):
                    if space['available'] == True:
                        self.logger.info('Found candidate with ' + str(space['max']) + ' max capacity! -> ' + space['server'])
                        candidates.append(space)

        if len(candidates) == 0:
            return self._response(404, 'SPACE NOT FOUND')

        return self._uploadchunkmastercandidate(hash=hash, chunks=chunks, index=1, max=len(chunks), name=name, candidates=candidates)

    def _uploadchunkmastercandidate(self, hash, chunks, index, max, name, candidates):

        if len(candidates) == 0:
            return self._response(400, 'SOME MIRRORS ARE UNAVIALABLE')

        self.logger.info('Uploading chunk (' + str(index) + ' of ' + str(max) + ') into master network...')

        current = candidates[0]
        candidates.remove(current)

        body = {'name': name, 'data': chunks[index - 1], 'partition': {'checksum': hash, 'index': index, 'max': max}}
        response = self._serverPutRequest(current['server'], '/chunks/upload', body)

        if response.status_code != 200:
            return self._uploadchunkmastercandidate(hash, chunks, index, max, name, candidates)

        self.logger.info('Chunk (' + str(index) + ' of ' + str(max) + ' was uploaded)!')

        if index == max:
            return self._message(200, 'UPLOADED')
        
        index += 1
        return self._uploadchunkmastercandidate(hash, chunks, index, max, name, candidates)

    def _uploadsinglemaster(self):

        body = request.json

        if not 'name' in body:
            return self._message(400, 'PARAMETER NAME IS REQUIRED')

        if not 'data' in body:
            return self._message(400, 'DATA IS REQUIRED')

        name = body['name']
        data = body['data']

        temp = secrets.token_hex(nbytes=16)
        b64data = base64.b64decode(data)

        if os.path.isfile("../files/" + temp):
            return self._message(409, 'FILE ALREADY EXISTS')

        f = open("../files/" + temp, "wb")
        f.write(b64data)
        f.close()

        hash = hs.fileChecksum("../files/" + temp, "sha256")
        size = os.path.getsize("../files/" + temp)

        self.logger.info('Finding space of (' + str(size) + ' bytes) in master...')
        response = self._masterRequest('/space/' + str(size))

        if response.status_code != 200:
            self.logger.error('Master status code is: ' + str(response.status_code))
            return self._response(500, 'MASTER IS OFFLINE')

        response = response.json()

        if not 'response' in response:
            return self._response(404, 'SPACE NOT FOUND')

        spaces = response['response']
        candidates = []

        for space in spaces:
            if space['server'] != (self._host + ':' + self._port):
                if space['available'] == True:
                    self.logger.info('Found candidate with ' + str(space['max']) + ' max capacity!')
                    candidates.append(space)

        if len(candidates) == 0:
            return self._response(404, 'SPACE NOT FOUND')

        return self._uploadsinglemastercandidate(b64=data, name=name, candidates=candidates)

    def _uploadsinglemastercandidate(self, b64, name, candidates):

        if len(candidates) == 0:
            return self._response(400, 'ALL MIRRORS ARE UNAVIALABLE')

        current = candidates[0]
        candidates.remove(current)

        body = {'name': name, 'data': b64}
        response = self._serverPutRequest(current['server'], '/upload', body)

        if response.status_code != 200:
            return self._uploadsinglemastercandidate(b64, name, candidates)

        return self._message(200, 'UPLOADED')

    def _uploadsingle(self):

        body = request.json

        if not 'name' in body:
            return self._message(400, 'PARAMETER NAME IS REQUIRED')

        if not 'data' in body:
            return self._message(400, 'DATA IS REQUIRED')

        name = body['name']
        data = body['data']

        try:

            temp = secrets.token_hex(nbytes=16)
            b64data = base64.b64decode(data)

            if os.path.isfile("../files/" + temp):
                return self._message(409, 'FILE ALREADY EXISTS')

            f = open("../files/" + temp, "wb")
            f.write(b64data)
            f.close()

            hash = hs.fileChecksum("../files/" + temp, "sha256")

            File = Query()
            results = self.files.search(File.hash == hash)

            if 'partition' in body:
                        
                if not 'checksum' in body['partition']:
                    return self._message(400, 'PARTITION CHEKSUM IS REQUIRED')

                if not 'index' in body['partition']:
                    return self._message(400, 'PARTITION INDEX IS REQUIRED')

                if not 'max' in body['partition']:
                    return self._message(400, 'PARTITION MAX IS REQUIRED')

                original_checksum = body['partition']['checksum'] 

                chunk_index = body['partition']['index']
                chunk_max = body['partition']['max']

            '''if len(results) == 0:

                self.files.insert({'type': 'one', 'hash': hash, 'uploadname': name, 'filename': temp})
                self.logger.info('Uploaded new file (' + hash + ')[' + name + '] into this node!')

                return self._message(200, 'UPLOADED')

            else:

                self.files.update({'type': 'one', 'hash': hash, 'uploadname': name, 'filename': temp}, File.hash == hash)
                self.logger.info('Replacing file (' + hash + ')[' + name + '] into this node!')

                return self._message(200, 'UPLOADED') '''

            self.files.insert({'type': 'one', 'hash': hash, 'uploadname': name, 'filename': temp})
            self.logger.info('Uploaded new file (' + hash + ')[' + name + '] into this node!')

            return self._message(200, 'UPLOADED')

        except binascii.Error:
            return self._message(400, 'INVALID PAYLOAD')

    def _remove(self, filename):

        if not os.path.isfile("../files/" + filename):
            return self._message(400, 'FILE NOT EXISTS')

        os.remove("../files/" + filename)
        return self._message(200, 'REMOVED')

    def _serverPutRequest(self, url, route, body):

        try:
            url = 'http://' + url + route
            return requests.put(url=url, json=body)
        except requests.exceptions.RequestException as e:
            return None

    def _serverPostRequest(self, url, route, body):

        try:
            url = 'http://' + url + route
            return requests.post(url=url, json=body)
        except requests.exceptions.RequestException as e:
            return None

    def _serverGetRequest(self, url, route):

        try:
            url = 'http://' + url + route
            return requests.get(url=url)
        except requests.exceptions.RequestException as e:
            return None

    def _masterRequest(self, route):

        try:
            url = self.config['master']['main'] + route
            return requests.get(url=url)
        except requests.exceptions.RequestException as e:
            try:
                url = self.config['master']['fallback'] + route
                return requests.get(url=url)
            except requests.exceptions.RequestException as e:
                return None

    def _response(self, code, json):
        return {'code': code, 'response': json}

    def _message(self, code, message):
        return {'code': code, 'message': message}

def run_server(hostname, port, config, logger):
    threading.Thread(target=th, args=[hostname, port, config, logger,], daemon=True).start()

def th(hostname, port, config, logger):
    server = Server(host=hostname, port=port, config=config, logger=logger)
    server.start()