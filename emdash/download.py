import Queue
import collections
import datetime
import functools
import getpass
import glob
import operator
import optparse
import os
import re
import sys
import time

# PyQt4 imports
from PyQt4 import QtGui, QtCore, Qt

# emdash imports
import emdash.config
import emdash.emmodels
import emdash.emwizard
import emdash.emthreads
import emdash.upload
import emdash.ui

class DownloadConfig(emdash.config.Config):
    applicationname = "EMDashDownload"
    pass

def main(appclass=None, configclass=None):
    appclass = appclass or BaseDownload
    configclass = configclass or DownloadConfig

    # Start the application
    emdash.config.setconfig(configclass)
    app = QtGui.QApplication(sys.argv)
    window = appclass()
    window.request_login(emdash.config.get('username'), emdash.config.get('password'))
    sys.exit(app.exec_()) 
    
##############################
# Base EMDash Uploader
##############################

class BaseDownload(emdash.upload.BaseTransport):
    ui = emdash.ui.Ui_Download.Ui_Download
    worker = emdash.emthreads.DownloadThread
    headers = ["name", "filename", "record", "_status"]
    headernames = ["Binary", "Filename", "Record", "Status"]
    headerwidths = [200, 200, 100, 100]
    
    def init(self):
        self._targets = []
        self.ui.button_grid.addAction(QtGui.QAction("Browse for destination", self, triggered=self._select_target_wizard))
        self.ui.button_grid.addAction(QtGui.QAction("Manually select destination", self, triggered=self._name_target_wizard))
        self.worker.start()
        
    @QtCore.pyqtSlot()
    def begin_session(self):
        super(BaseDownload, self).begin_session()
        for target in self._targets:
            self.set_target(target)

    @QtCore.pyqtSlot(unicode)
    def set_target(self, name):
        try:
            rec = emdash.config.db().record.get(name)
        except Exception, e:
            self.signal_exception.emit(unicode(e))
            return
        self.target = rec.get('name')
        self.recs[rec.get('name')] = rec
        self.signal_status.emit(rec.get('name'), rec)
        self.signal_target.emit(self.target)
        self.update_ui()
        self._set_download(self.target)

    def _set_download(self, name):
        # Download
        recurse = -1
        bdos = []
        if recurse != 0:
            recs = [name]
            recs += emdash.config.db().rel.children(name, recurse=recurse)
        else:
            recs = [name]
        self.log("Found recs: %s"%len(recs))

        bdos = emdash.config.db().binary.find(record=recs, count=0)
        self.log("Found bdos: %s"%len(bdos))
        for bdo in bdos:
            self.newfile(bdo.get('name'), bdo)

    @QtCore.pyqtSlot(unicode, object)
    def newfile(self, name, data=None):
        name = unicode(name) # qstrings.. >:/
        data = data or {}
        data['_target'] = self.target
        self.files[name] = data
        self.signal_newfile.emit(name, data)
        self.queue.put((name, data))

if __name__ == '__main__':
    main()

