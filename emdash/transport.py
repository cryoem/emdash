#!/usr/bin/python
import base64
import httplib
import json
import mimetools
import mimetypes
import os
import socket
import stat
import time
import urllib
import urllib2
import cStringIO as StringIO

import emdash.config

class UploadFile(file):
    def __init__(self, *args, **kwargs):
        name_upload = kwargs.pop('name_upload', None)
        name_prefix = kwargs.pop('name_prefix', None)
        super(UploadFile, self).__init__(*args, **kwargs)
        self.name_upload = os.path.basename(name_upload or self.name)
        if name_prefix:
            self.name_upload = name_prefix + self.name_upload

class Handler(object):       
    def __init__(self, headers=None, log=None):
        self.headers = headers or {} 
        self.headers['User-Agent'] = emdash.config.get('USER_AGENT')
        self.log = log or (lambda x:x)
        
    def _data_files(self, data):
        data = data or {}
        files = {}
        newdata = {}
        for k,v in data.items():
            if isinstance(v, file):
                files[k] = v
            else:
                newdata[k] = v
        return newdata, files
        
class DownloadHandler(Handler):
    pass

class PutHandler(Handler): 
    def open(self, path, data=None):
        """Implements Transfer-Encoding:Chunked over a PUT request."""
        data, files = self._data_files(data)
        
        # Get the file
        if len(files) != 1:
            raise Exception, "Must provide exactly ONE file for a HTTP PUT request."

        fileparam, fileobj = files.items()[0]
        try:    
            filesize = os.fstat(fileobj.fileno()).st_size
        except:
            filesize = 0
        
        # Allow alternate names for upload.
        try:
            filename = fileobj.name_upload
        except AttributeError:
            filename = fileobj.name

        # Encode all the parameters in a query string.
        path = "%s?%s"%(path, urllib.urlencode(data))
        
        # Add special headers..
        self.headers['Transfer-Encoding'] = 'chunked'
        self.headers['X-File-Param'] = fileparam
        self.headers['X-File-Name'] = os.path.basename(filename)
    
        # Open connection
        # httplib doesn't take scheme://
        host = emdash.config.get('host').partition('://')[-1] 
        http = httplib.HTTPConnection(host)
        http.request('PUT', path, headers=self.headers)
    
        # Upload in chunks
        chunksize = 128*1024        
        while True:
            try:
                chunk = fileobj.read(chunksize)
                http.send('%X\r\n'%(len(chunk)))
                http.send(chunk)
                http.send('\r\n')
                self.log(progress=(fileobj.tell()/float(filesize or 1)))
            except socket.error:
                raise
            if not chunk:
                break
    
        # Return response...
        return http.getresponse()

class PostHandler(Handler):
    # Loosely based on http://code.activestate.com/recipes/146306/
    def open(self, path, data=None):
        """Upload using multipart form encoding."""
        data, files = self._data_files(data)

        # Set MIME boundary.
        self.boundary = mimetools.choose_boundary()
        self.headers['Content-Type'] = 'multipart/form-data; boundary=%s'%self.boundary
        
        # In the future, use Transfer-Encoding:Chunked as in PutHandler.
        # This should work, but I don't know how well it's supported when also using mutlipart/form-data.
        # Important note:
        #   This will create a string the size of all the files to upload. This can crash on 32-bit Python,
        #   especially on Windows.
        body = self.encode_multipart_formdata(data, files)

        # seek to end to get size...
        body.seek(0, os.SEEK_END)
        size = body.tell()
        body.seek(0)
        self.headers['Content-Length'] = str(size)
        
        # Open connection
        # httplib doesn't take scheme://
        host = emdash.config.get('host').partition('://')[-1] 
        http = httplib.HTTPConnection(host)
        http.request('POST', path, headers=self.headers)

        # Upload in chunks so we can show progress.
        chunksize = 128*1024        
        pos = 0
        while True:
            try:
                chunk = body.read(chunksize)
                pos = pos+len(chunk)
                http.send(chunk)
                self.log(progress=(pos/float(size or 1)))
            except socket.error:
                raise
            if not chunk:
                break

        # Return response...
        return http.getresponse()
                
    def encode_multipart_formdata(self, data, files):
        buf = StringIO.StringIO()
        for(key, values) in data.items()+files.items():
            values = self._check_iterable(values)
            for value in values:
                if hasattr(value, 'read'):
                    # Allow alternate names for upload.
                    try:
                        filename = value.name_upload
                    except AttributeError:
                        filename = value.name                    
                    buf.write('--%s\r\n'%self.boundary)
                    buf.write('Content-Disposition: form-data; name="%s"; filename="%s"\r\n'%(key, unicode(os.path.basename(filename)).encode('utf-8')))
                    buf.write('Content-Type: application/octet-stream\r\n')
                    buf.write('\r\n')

                    value.seek(0)
                    chunk = value.read()
                    total = len(chunk)
                    while chunk:
                        buf.write(chunk)
                        chunk = value.read(1024*1024)
                        total += len(chunk)
                    buf.write('\r\n')
                else:
                    buf.write('--%s\r\n'%self.boundary)
                    buf.write('Content-Disposition: form-data; name="%s"\r\n'%key)
                    buf.write('\r\n')
                    buf.write(unicode(value).encode('utf-8'))
                    buf.write('\r\n')

        buf.write('--%s--\r\n\r\n'%self.boundary)
        return buf
    
    def _check_iterable(self, value):
        # Grumble..
        if isinstance(value, file):
            return [value]
        if not hasattr(value, "__iter__"):
            return [value]
        return value
    
    def get_content_type(self, filename):
        return 'application/octet-stream'
