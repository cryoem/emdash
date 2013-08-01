import Queue
import collections
import datetime
import json
import operator
import os
import time

from PyQt4 import QtCore

import emdash.config
import emdash.log
import emdash.handlers

class DBThread(QtCore.QThread):
    signal_status = QtCore.pyqtSignal(unicode, object)
    signal_exception = QtCore.pyqtSignal(unicode)
    def __init__(self, method, args):
        pass
        
class ClockThread(QtCore.QThread):
    """Emit a signal every second with timedelta from start time"""
    signal_tick = QtCore.pyqtSignal(str)

    def __init__(self, starttime=None, parent=None):
        QtCore.QThread.__init__(self, parent=parent)
        self.starttime = starttime
        
    def reset(self):
        self.starttime = time.time()
        
    def run(self):
        self.reset()
        while True:
            if self.starttime == None:
                t = ""
            else:
                t = int(time.time() - self.starttime)
                t = str(datetime.timedelta(seconds=t))

            self.signal_tick.emit(t)        
            time.sleep(1)

    @QtCore.pyqtSlot()    
    def longsleep(self):
        self.sleep(5)


class FSPollThread(QtCore.QThread):
    """Watch a directory"""
    signal_newfile = QtCore.pyqtSignal(unicode, object)

    def __init__(self, parent=None): #queue=None, 
        """Watches a directory for new files"""
        QtCore.QThread.__init__(self, parent=parent)
        self.handler = emdash.handlers.get_handler(emdash.config.get("handler"))
        
    @QtCore.pyqtSlot(unicode, bool, bool)
    def set_path(self, path, existing=True, watch=True):
        self.handler.set_path(path)
        if not existing:
            f = self.handler.poll()
            emdash.log.msg("Ignoring %s existing items.."%len(f))
        if watch:
            self.start()
        else:
            self._run()
            
    def _run(self):
        for f in self.handler.poll():
            self.found(f)        
            
    def run(self):
        while True:
            self._run()
            time.sleep(5)

    @QtCore.pyqtSlot(unicode)
    def found(self, name):
        # Signal that we have a new file, with some basic info
        name = unicode(name)
        # Get the appropriate handler
        h = self.handler.new(name=name)
        if not h:
            return
        data = {}
        data['_name'] = h.name
        data['_filename'] = h.display_filename()
        data['_recname'] = h.display_name()
        data['_enqueue'] = h.auto_enqueue()
        self.signal_newfile.emit(h.name, data)

    @QtCore.pyqtSlot(QtCore.QStringList)
    def founds(self, filenames):
        for filename in filenames:
            self.found(filename)

class UploadThread(QtCore.QThread):
    """Upload a file."""
    signal_failure = QtCore.pyqtSignal(unicode, unicode)
    signal_success = QtCore.pyqtSignal(unicode, object)    
    signal_status = QtCore.pyqtSignal(unicode, object)

    def __init__(self, parent=None, queue=None):
        self.queue = queue
        self.handler = emdash.handlers.get_handler(emdash.config.get("handler"))
        QtCore.QThread.__init__(self, parent=parent)

    def run(self):        
        while True:
            self.action()

    def action(self):
        name, data = self.queue.get()
        target = data.get('_target') # upload target

        if not target:
            raise Exception, "UploadThread: Invalid record name for upload: %s"%target

        # Get the handler and upload
        dbt = self.handler.new(name=name, data=data)

        # Wait a small amount of time before proceeding..
        dbt.setwait(emdash.config.get('sleeptime'))

        try:
            rec = dbt.upload()
        except Exception, e:
            emdash.log.error("UploadThread exception: %s"%e, exception=e)
            self.signal_failure.emit(name, unicode(e))
            self.queue.put((name, data))
            time.sleep(emdash.config.get('sleeptime'))
        else:
            self.signal_success.emit(name, rec)
        self.queue.task_done()

class DownloadThread(UploadThread):
    signal_failure = QtCore.pyqtSignal(unicode, unicode)
    signal_success = QtCore.pyqtSignal(unicode, object)    
    signal_status = QtCore.pyqtSignal(unicode, object)    
    
    def action(self):
        name, data = self.queue.get()    
        dbt = emdash.handlers.FileHandler(name=name, data=data)
        try:
            dbt.download()
        except Exception, e:
            emdash.log.error("DownloadThread exception: %s"%e, exception=e)
            self.signal_failure.emit(filename, unicode(e))
            self.queue.put((name, data))
        self.queue.task_done()
        