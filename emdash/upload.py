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
import json

# PyQt4 imports
from PyQt4 import QtGui, QtCore, Qt

# emdash imports
import emdash.config
import emdash.log
import emdash.emmodels
import emdash.emwizard
import emdash.emthreads
import emdash.ui

# handlers
import emdash.handlers
import emdash.emhandlers

class UploadConfig(emdash.config.Config):
    applicationname = "EMDashUpload"
    def add_options(self, parser):
        parser.add_argument("--session_protocol", "-t", 
            help="Session type. Available: base, microscopy, scan")
        self.defaults['session_protocol'] = 'microscopy'    
        
        # These get no default.
        parser.add_argument("--handler", "-r", 
            help="Handler. Examples: ccd, ddd, micrograph")
        parser.add_argument("--microscope", "-m", 
            help="Microscope or Microscope folder Record name")
        parser.add_argument("--target", 
            help="Specify upload target directly.")
        parser.add_argument("--watch", 
            help="Watch directory for files to upload")

def main(appclass=None, configclass=None):
    appclass = appclass or BaseUpload
    configclass = configclass or UploadConfig
    # Start the application
    emdash.config.setconfig(configclass)
    app = QtGui.QApplication(sys.argv)
    window = appclass()
    window.request_login(emdash.config.get('username'), emdash.config.get('password'))
    sys.exit(app.exec_())    
    
##############################
# Some dialogs: Warning, Login, ...
##############################

def confirm(parent=None, title='Confirm', text=''):
    reply = QtGui.QMessageBox.question(
        parent, 
        title,
        text, 
        QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
        QtGui.QMessageBox.No
        )

    if reply == QtGui.QMessageBox.Yes:
        return True
    else:
        return False

class Options(QtGui.QDialog):
    def __init__(self, parent=None):
        self.widgets = {}
        QtGui.QDialog.__init__(self, parent=parent)        
        self.ui = emdash.ui.Ui_Options.Ui_Options()
        self.ui.setupUi(self)
        self.setupUi()

    def _addhr(self, layout):
        hr = QtGui.QFrame()
        hr.setFrameShape(QtGui.QFrame.HLine)
        hr.setFrameShadow(QtGui.QFrame.Sunken)        
        layout.addRow(hr)
    
    def _addtext(self, layout, text):
        q = QtGui.QLabel()
        q.setTextFormat(QtCore.Qt.RichText)
        q.setText(text)
        q.setWordWrap(True)
        q.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding);
        layout.addRow("", q)

    def setupUi(self):
        self.widgets['host'] = QtGui.QLineEdit();
        self.widgets['handler'] = QtGui.QLineEdit();
        self.widgets['microscope'] = QtGui.QLineEdit();
        self.widgets['session_protocol'] = QtGui.QLineEdit();
        for k, v in self.widgets.items():
            v.setText(emdash.config.get(k) or "")

        f = self.ui.layout_options
        f.addRow("Host:", self.widgets['host'])
        self._addtext(f, """The address to the EMEN2 server.""")        
        self._addhr(f)
        f.addRow("Handler:", self.widgets['handler'])
        self._addtext(f, """EMDash provides special handlers for some specific data acquisition packages. Use "ccd" for DM3, "ddd" for Direct Electron Detector, "serielem" for Seriel EM, and "jadas" for JADAS. If no handler is specified, EMDash will attempt to select one automatically based on file type.""")
        self._addhr(f)
        f.addRow("Session protocol:", self.widgets['session_protocol'])
        self._addtext(f, """This is the protocol that will be used when creating a new session. The default, "microscopy", is a protocol for a generic electron microscope. You may change this to a protocol that is specific to the instrument you are using.""")        
        f.addRow("Microscope:", self.widgets['microscope'])
        self._addtext(f, """This is the record ID for the microscope. New sessions will be created as children of this record. EMDash will also check for child record with date-specific configuration.""")
        self._addhr(f)
        self._addtext(f, """You must restart EMDash for changes to take effect. EMDash will quit when you save this form.""")
        
    def accept(self):
        ret = {}
        for k,v in self.widgets.items():
            value = unicode(v.text())
            # Write to the config file.
            emdash.config.config.write(k, value)
        self.done(0)        
        sys.exit(0)
    
class DWarning(QtGui.QDialog):
    def __init__(self, displayname=None, session=None, parent=None):
        QtGui.QDialog.__init__(self, parent=parent)        
        self.ui = emdash.ui.Ui_Warning.Ui_Warning()
        self.ui.setupUi(self)
        self.ui.label_user.setText(unicode(displayname))
        self.ui.label_session.setText("""
            <a href="%s/record/%s/">%s</a>
            """%(emdash.config.get('host'), session, session))

    def closeEvent(self, event):
        event.ignore()

class Login(QtGui.QDialog):
    # Login signals
    signal_trylogin = QtCore.pyqtSignal(unicode, unicode)    
    signal_login = QtCore.pyqtSignal()
    signal_login_exception = QtCore.pyqtSignal(unicode)
    signal_logout = QtCore.pyqtSignal()

    def __init__(self, authmsg=None, parent=None):
        QtGui.QDialog.__init__(self, parent=parent)        
        self.ui = emdash.ui.Ui_Login.Ui_Login()
        self.ui.setupUi(self)

        self.ui.label_version.setText("""<a href="%s">EMDash v%s</a>"""%("http://blake.grid.bcm.edu/emanwiki/EMEN2", emdash.__version__))
        self.ui.button_options.clicked.connect(self.showoptions)
        self.signal_trylogin.connect(self.login)
        self.signal_login.connect(self.ok)
        self.signal_login_exception.connect(self.error)

        if authmsg:
            self.ui.label_login.setText(authmsg)
        else:
            self.ui.label_login.setText('Login: %s'%emdash.config.get('host'))            

    @QtCore.pyqtSlot()
    def ok(self):
        self.done(0)

    @QtCore.pyqtSlot(unicode)
    def error(self, e):
        self.ui.label_login.setText(e)

    def accept(self):        
        self.ui.label_login.setText("Logging in...")
        
        # Attempt to login
        self.signal_trylogin.emit(
            unicode(self.ui.edit_name.text()),
            unicode(self.ui.edit_password.text()))    

        self.ui.edit_password.clear()

    @QtCore.pyqtSlot(unicode, unicode)
    def login(self, username=None, password=None):
        # Attempt to clear any login
        emdash.config.set('ctxid','')

        # Attempt to login
        try:
            db = emdash.config.login(username=unicode(username), password=unicode(password))
            username, groups = db.auth.check.context()
            emdash.log.msg("Logged in:", username, groups)
        except Exception, e:
            self.error("Login failure: %s"%e)
            emdash.log.error("Login failure: %s"%e, exception=e)
            self.show()
            try:
                msg = e.msg
            except:
                msg = unicode(e)
            self.signal_login_exception.emit(msg)
            return

        # Login callbacks
        self.signal_login.emit()

    def showlogin(self, username=None, password=None):
        if username != None and password != None:
            return self.login(username, password)
            
        if username:
            self.ui.edit_name.setText(username)
        if password:
            self.ui.edit_password.setText(password)

        self.show()
        
    def showoptions(self):
        l = Options(parent=self)
        l.show()

##############################
# Base EMDash Uploader
##############################

class BaseTransport(QtGui.QMainWindow):
    # Base class for an Upload UI
    ui = emdash.ui.Ui_Upload.Ui_Upload
    worker = emdash.emthreads.UploadThread
    
    # Session controls
    signal_begin_session = QtCore.pyqtSignal()
    signal_end_session = QtCore.pyqtSignal()
    signal_target = QtCore.pyqtSignal(unicode)

    # Updated record
    signal_newfile = QtCore.pyqtSignal(unicode, object)
    signal_status = QtCore.pyqtSignal(unicode, object)
    signal_exception = QtCore.pyqtSignal(unicode)
    
    # Files
    signal_set_path = QtCore.pyqtSignal(unicode, bool, bool)

    # Table headers
    headers = ["_recname", "_status"]
    headernames = ["Name", "Status"]
    headerwidths = [400,200]

    def __init__(self, parent=None):
        super(BaseTransport, self).__init__(parent=parent)

        # File / queue
        self.path = None        
        self.end = False        

        # Current targets
        self.files = {}
        self.names = {}
        self.target = None
        
        # Cache
        self.recs = {}
        self.recnames = {}
        self.settings = {}
        
        # Listen for progress events.
        emdash.log.add_listener(self.log_listener)
        
        ###### Queue
        self.queue = Queue.Queue()
        self.queuemodel = emdash.emmodels.QueueModel(
            parent=self, 
            headers=self.headers, 
            headernames=self.headernames)
        
        ###### Setup UI
        self.ui = self.ui()
        self.ui.setupUi(self)
        
        ###### Worker threads
        # Starts when a new session is made
        self.clockthread = emdash.emthreads.ClockThread()
        self.clockthread.signal_tick.connect(self.tock, type=QtCore.Qt.QueuedConnection)
        self.signal_begin_session.connect(self.clockthread.start, type=QtCore.Qt.QueuedConnection)

        # Send any updates to the queue model/view
        self.worker = self.worker(queue=self.queue)
        self.worker.signal_status.connect(self.queuemodel.file_status, type=QtCore.Qt.QueuedConnection)
        self.worker.signal_success.connect(self.queuemodel.file_success, type=QtCore.Qt.QueuedConnection)
        self.worker.signal_failure.connect(self.queuemodel.file_failure, type=QtCore.Qt.QueuedConnection)

        self.signal_newfile.connect(self.queuemodel.newfile, type=QtCore.Qt.QueuedConnection) # add to table
        self.signal_newfile.connect(self.ui.tree_files.newfile, type=QtCore.Qt.QueuedConnection) # scroll to bottom
        self.signal_status.connect(self.queuemodel.file_status, type=QtCore.Qt.QueuedConnection) # update table

        # New upload target
        self.signal_target.connect(self.queuemodel.set_target, type=QtCore.Qt.QueuedConnection)
        self.signal_target.connect(self.worker.start, type=QtCore.Qt.QueuedConnection)

        # FSPollThread starts whenever a directory is selected
        self.fspollthread = emdash.emthreads.FSPollThread()
        self.fspollthread.signal_newfile.connect(self.newfile, type=QtCore.Qt.QueuedConnection) # add to the upload queue
        self.signal_set_path.connect(self.fspollthread.set_path, type=QtCore.Qt.QueuedConnection) # set watch path
        # todo: set_path has a watch keyword argument that will start the thread.
        # self.signal_set_path.connect(self.fspollthread.start, type=QtCore.Qt.QueuedConnection) # start polling

        ###### UI
        self.ui.button_session.addAction(QtGui.QAction("Logout", self, triggered=self.close))

        # File control widget
        self.ui.tree_files.signal_set.connect(self.set, type=QtCore.Qt.QueuedConnection)
        self.ui.tree_files.signal_enqueue.connect(self.enqueue, type=QtCore.Qt.QueuedConnection)    
        self.ui.tree_files.prog_column(len(self.headers)-1)
        self.ui.tree_files.setModel(self.queuemodel)
        for count, width in enumerate(self.headerwidths or []):
            self.ui.tree_files.setColumnWidth(count, width)
        
        self.init()

    def init(self):
        pass

    @QtCore.pyqtSlot(unicode, object)
    def enqueue(self, name, data):
        # Get the stored file..
        name = unicode(name)
        data = self.files.get(name) or data
        data["_status"] = "Queued"
        self.queue.put((name, data))
        self.signal_status.emit(name, data)

    @QtCore.pyqtSlot(unicode, object)
    def newfile(self, name, data=None):
        # This is the receiver for FSPollThread's signal_newfile.
        # First argument is the item ID
        # Second argument is a dictionary
        name = unicode(name) # qstrings.. >:/
        data = data or {}
        data['_target'] = self.target
        data.update(self.settings)
        # Store reference (for queue/dequeue)
        self.files[name] = data

        # Broadcast the new file
        self.signal_newfile.emit(name, data)

        # Add this name and data to the action queue.
        if data.get('_enqueue'):
            self.queue.put((name, data))

    @QtCore.pyqtSlot()
    def update_ui(self):
        """Update the current set of records."""
        rnget = filter(None, self.names.values())

        if self.target:
            rnget.append(self.target)
        
        try:
            recs = emdash.config.db().record.get(rnget)
        except Exception, e:
            emdash.log.error("Couldn't get records: %s"%e, exception=e)
        else:
            for rec in recs:
                self.recs[rec.get('name')] = rec

        try:
            rn = emdash.config.db().record.render(rnget)
        except Exception, e:
            emdash.log.error("Couldn't get rendered views: %s"%e, exception=e)
        else:
            self.recnames.update(rn)

        if self.target:
            ready = True
        else:
            ready = False
            
        try:    
            self.ui.button_path.setEnabled(ready)
        except:
            pass
        try:
            self.ui.label_grid.setText(self.getlabel(name=self.target))        
        except:
            pass

    @QtCore.pyqtSlot(str)
    def error(self, e):
        error = QtGui.QMessageBox(parent=self)
        error.setWindowTitle("Error")
        error.setText(unicode(e))
        error.setIcon(QtGui.QMessageBox.Critical)
        error.exec_()

    def log_listener(self, *msg, **kwargs):
        name = kwargs.get('name', None)
        status = kwargs.get('progress') or ' '.join(map(unicode, msg))
        if name:
            self.signal_status.emit(name, {'_status':status})

    ###############################
    # Editing records / Comments
    ###############################

    @QtCore.pyqtSlot(unicode, unicode, unicode)
    def set(self, name, param, value):
        # print "Setting:", name, param, value
        if name < 0:
            self.signal_exception.emit("Cannot update non-existent record")
            return        

        try:
            rec = emdash.config.db().record.update(name, {unicode(param): unicode(value)})
        except Exception, inst:
            self.signal_exception.emit("Cannot update record: %s"%inst)
        else:
            if rec:
                self.signal_status.emit(unicode(rec.get('name')), rec)

        if param == 'comments':
            self.update_comments()
            
    @QtCore.pyqtSlot()
    def update_comments(self):
        pass

    @QtCore.pyqtSlot(object, object)
    def edit_records(self, editrecords, selectrecords):        
        try:
            updrecs = emdash.config.db().record.put(editrecords)
        except Exception, e:
            self.signal_exception.emit(unicode(e))
            return

        self.names.update(selectrecords or {})
        for rec in updrecs:
            self.recs[rec.get('name')] = rec
            self.names[rec.get('rectype')] = rec.get('name')
            self.signal_status.emit(unicode(rec.get('name')), rec)
            
        # this is an ugly hack
        self._check_target()    
        
        # Update the UI
        self.update_ui()

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

        if emdash.config.get("watch"):
            self.check_path(emdash.config.get("watch"))

    def _check_target(self):
        return

    @QtCore.pyqtSlot(unicode)
    def set_setting(self, value, param=None):
        if not param:
            return
        if not value:
            del self.settings[str(param)]
        self.settings[str(param)] = str(value)

    ##############################
    # Session Management
    ##############################

    def request_login(self, username=None, password=None, authmsg=None):
        # Get login info for new session
        l = Login(parent=self, authmsg=authmsg)
        l.signal_login.connect(self.login_cb)
        l.showlogin(username=username, password=password)

    @QtCore.pyqtSlot()
    def login_cb(self):
        self.update_ui()
        self.show()
        self.begin_session()

    @QtCore.pyqtSlot()
    def begin_session(self):
        self.signal_begin_session.emit()
        if emdash.config.get('target'):
            self.set_target(emdash.config.get('target'))
            
    @QtCore.pyqtSlot()    
    def end_session(self):
        emdash.log.msg("Logging out!")
        emdash.config.db().auth.logout()
        self.close()
    
    @QtCore.pyqtSlot(str)    
    def tock(self, t):
        # Update session clock
        target = self.names.get(emdash.config.get('session_protocol'))
        if t == None:
            t = ""
        elif target > -1:
            t = """<a href="%s/record/%s/?ctxid=%s">%s</a>"""%(emdash.config.get('host'), target, emdash.config.get('ctxid'), t)    
        else:
            t = """<a href="%s?ctxid=%s">%s</a>"""%(emdash.config.get('host'), emdash.config.get('ctxid'), t)    
        self.ui.label_session.setText(t)

    #####################
    # Event handlers
    #####################
    
    def closeEvent(self, event):
        accept = confirm(parent=self, title="Logout", text="Are you sure you want to logout? Any pending transfers will be cancelled.")
        if accept:
            self.end_session()
            event.accept()
        else:
            event.ignore()

    #####################
    # Base Wizards
    #####################

    @QtCore.pyqtSlot()
    def _select_target_wizard(self):
        wizard = emdash.emwizard.SelectAnyWizard(parent=self, selected=self.names)
        wizard.signal_any.connect(self.set_target, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()         
                
    @QtCore.pyqtSlot()
    def _name_target_wizard(self):
        d = QtGui.QInputDialog(self)
        d.setLabelText("Record Name")
        d.textValueSelected.connect(self.set_target, type=QtCore.Qt.QueuedConnection)
        d.exec_()

    #####################
    # Misc.
    #####################
            
    def getlabel(self, name=None, rectypes=None):
        """return the name/recname link for the first rectype found"""
        
        if not name:
            if not hasattr(rectypes, "__iter__"):
                rectypes = [rectypes]
            for r in rectypes:
                if self.names.get(r) != None:
                    name = self.names.get(r)

        if name:
            return """<a href="%s/record/%s?ctxid=%s">%s</a>"""%(emdash.config.get('host'), name, emdash.config.get('ctxid'), self.recnames.get(str(name), name))

        return ""

    def connect_slider(self, i, factor=1000.0):
        slider = getattr(self.ui, 'slider_%s'%i)
        edit = getattr(self.ui, 'edit_%s'%i)
        slider.sliderMoved.connect(functools.partial(self._slider_to_edit, target=edit, factor=factor), type=QtCore.Qt.QueuedConnection)
        edit.textChanged.connect(functools.partial(self._edit_to_slider, target=slider, factor=factor), type=QtCore.Qt.QueuedConnection)
        edit.textChanged.connect(functools.partial(self.set_setting, param=i), type=QtCore.Qt.QueuedConnection)        

    def _slider_to_edit(self, i, target=None, factor=1.0):
        try:
            i = i / factor
        except:
            i = 0
        target.setText(str(i))

    def _edit_to_slider(self, i, target=None, factor=1.0):
        try:
            i = float(i) * factor
        except:
            i = 0
        target.setValue(int(float(i or 0)))    

class BaseUpload(BaseTransport):
    def init(self):
        sp_existing_watch = functools.partial(self._set_path, existing=True, watch=True)
        sp_watch = functools.partial(self._set_path, existing=False, watch=True)
        sp_existing = functools.partial(self._set_path, existing=True, watch=False)
        sp = functools.partial(self._set_path, existing=False, watch=False)

        self.ui.button_path.addAction(QtGui.QAction("Select directory", self, triggered=sp_existing_watch))        
        self.ui.button_path.addAction(QtGui.QAction("Select directory, new files only", self, triggered=sp_watch))
        # self.ui.button_path.addAction(QtGui.QAction("Select directory, existing files only", self, triggered=sp_existing))
        self.ui.button_path.addAction(QtGui.QAction("Add files", self, triggered=self._add_files))

        self.ui.button_grid.addAction(QtGui.QAction("Browse for destination", self, triggered=self._select_target_wizard))
        self.ui.button_grid.addAction(QtGui.QAction("Manually select destination", self, triggered=self._name_target_wizard))

    #####################
    # Comments
    #####################

    @QtCore.pyqtSlot(unicode)
    def addcomment(self, rectype):
        # Add a comment to a known record
        comment = self.ui.edit_addcomment.toPlainText()    

        name = self.names.get(rectype, -1)
        if name < 0:
            self.error("Could not add comment because there was no %s record yet for this session."%rectype)
            return

        self.ui.button_addcomment.setEnabled(False)
        self.ui.edit_addcomment.setEnabled(False)
        self.set(name, "comments", comment)

    #####################
    # Signals to FS Poll Thread
    #####################

    @QtCore.pyqtSlot()
    def _add_files(self):
        # Select directory to watch for queue
        d = QtGui.QFileDialog(self)
        d.setFileMode(QtGui.QFileDialog.ExistingFiles)
        d.filesSelected.connect(self.fspollthread.founds, type=QtCore.Qt.QueuedConnection)
        d.filesSelected.connect(self.fspollthread.start, type=QtCore.Qt.QueuedConnection)                
        d.exec_()

    @QtCore.pyqtSlot()
    def _set_path(self, existing=True, watch=True):
        # Select directory to watch for queue
        cb = functools.partial(self.check_path, existing=existing, watch=watch)
        d = QtGui.QFileDialog(self)
        d.setFileMode(QtGui.QFileDialog.Directory)
        d.fileSelected.connect(cb, type=QtCore.Qt.QueuedConnection)
        d.exec_()

    @QtCore.pyqtSlot(unicode)
    def check_path(self, path, existing=True, watch=True):
        """Check for any existing files in the path."""
        path = unicode(path)
        emdash.log.msg("Checking path:", path)
        handler = emdash.handlers.get_handler(emdash.config.get("handler"))
        handler.set_path(path)
        # found = {}
        # for f in handler.poll():
        #     jsonfile = '%s.json'%f
        #     data = {}
        #     if os.path.exists(jsonfile):
        #         data = json.load(file(jsonfile,"r")) or {}
        #         emdash.log.msg("found: %s already uploaded to record: %s"%(f, data.get('name')))
        #         found[f] = data.get('name')                
        #     
        # if existing and found:
        #     text = 'Found %s files that have already been uploaded (see console for details.) These files will be skipped and not uploaded again. To re-upload these files, remove the json files to clear the references.\n\nContinue?'%len(found)
        #     accept = confirm(parent=self, title="Warning", text=text)
        # else:
        #     accept = True
        # 
        # if not accept:
        #     return 
        self.ui.label_path.setText(unicode(path))
        self.signal_set_path.emit(unicode(path), existing, watch)

if __name__ == '__main__':
    main()
