import sys
import os
import re
import traceback
import time

import datetime
import dateutil
import dateutil.tz

from PyQt4 import Qt, QtGui, QtCore

import emdash.config
import emdash.log
import emdash.emmodels
import emdash.ui

VIEW_REGEX = '(\$(?P<type>.)(?P<name>[\w\-]+)(?:="(?P<def>.+)")?(?:\((?P<args>[^$]+)?\))?(?P<sep>[^$])?)|((?P<text>[^\$]+))'

def error(e):
    error = QtGui.QMessageBox()
    error.setWindowTitle("Error")
    error.setText(unicode(e))
    error.setIcon(QtGui.QMessageBox.Critical)
    error.exec_()

################################
# DB-connected editing items
################################

def edititem(parent=None, pd=None, value=None, name=None):
    """Based on paramdef pd, return a widget suitable for 
    entering a db vartype"""
    
    vt = pd.get("vartype")

    map_edititem_vt = {
        DBQComboBox: ['int', 'float', 'percent', 'string', 'choice'],
        DBQDateTimeEdit: ["time","date","datetime"],
        DBQTextEdit: ["html","text", "comments"]
        # NoEdit: ['user', 'acl', 'groups', 'links', ]
    }
    
    map_vt_edititem = {}
    for k,v in map_edititem_vt.items():
        for v2 in v:
            map_vt_edititem[v2]=k
            
    return map_vt_edititem.get(vt, DBQNoEdit)(
        parent=parent, 
        value=value, 
        pd=pd)
    
class DBQNoEdit(QtGui.QLabel):
    def __init__(self, parent, value=None, pd=None):
        super(DBQNoEdit, self).__init__(parent)
        self.value = str(value or '')
        self.pd = pd
        self.setMinimumWidth(400)
        self.setText(self.value)
    
    def getvalue(self):
        return unicode(self.value)

# class DBQDateTimeEdit(QtGui.QDateTimeEdit):
class DBQDateTimeEdit(QtGui.QLineEdit):
    def __init__(self, parent, value=None, pd=None):
        super(DBQDateTimeEdit, self).__init__(parent)        
        self.setMinimumWidth(400)
        self.pd = pd
        if self.pd.get('name') == 'date_occurred':
            value = datetime.datetime.now(dateutil.tz.tzlocal()).replace(microsecond=0).isoformat()

        self.value = str(value or '')
        self.setText(self.value)
        # cdt = QtCore.QDateTime.currentDateTime()
        # self.setDateTime(cdt)
        # self.setCalendarPopup(True)
        # self.setDisplayFormat("yyyy-mm-dd hh:mm:ss")
        
    def getvalue(self):
        return unicode(self.text())

class DBQLineEdit(QtGui.QLineEdit):
    def __init__(self, parent, value=None, pd=None):
        super(DBQLineEdit, self).__init__(parent)
        self.value = str(value or '')
        self.pd = pd
        self.setMinimumWidth(400)
        self.setText(self.value)
    
    def getvalue(self):
        return unicode(self.text())

class DBQTextEdit(QtGui.QTextEdit):
    def __init__(self, parent, value=None, pd=None):
        super(DBQTextEdit, self).__init__(parent)
        self.value = str(value or '')
        self.pd = pd
        self.setMinimumWidth(400)        
        self.setText(self.value)
    
    def getvalue(self):
        return unicode(self.toPlainText())
            
class DBQComboBox(QtGui.QComboBox):
    def __init__(self, parent, value=None, pd=None):
        """This is a QComboBox that fetches items from a DB query"""
        super(DBQComboBox, self).__init__(parent)
        QtCore.QObject.connect(
            self, 
            QtCore.SIGNAL('textEdited(QString)'), 
            self.text_changed)
            
        self.setEditable(True)
        self.value = str(value or '')
        self.pd = pd
        self.setMinimumWidth(400)

        vt = self.pd.get("vartype")
        if vt == "choice":
            for item in self.pd.get("choices",[]):
                self.insertItem(0, item)
            self.setEditText(self.value)        
            self.setEditable(False)        
        elif vt == "boolean":
            self.insertItem(0, "")
            self.insertItem(0, "True")
            self.insertItem(0, "False")
            self.setEditText(self.value)
            self.setEditable(False)        
        elif vt == "user":
            name = emdash.config.db().auth.check.context()[0]
            self.insertItem(0, name)
            self.setEditText(self.value)
        elif self.pd.get("indexed"):
            self.query()
            self.setEditText(self.value)
        else:
            self.setEditText(self.value)

        self.setCompleter(None)
        self.setMaximumSize(500,100)
    
    def query(self):    
        self.query = emdash.config.db().record.findbyvalue(self.pd.get("name"))
        self.query = [unicode(i[0]) for i in sorted(self.query)]
        self.insertItem(0, "")
        for i in self.query:
            self.insertItem(0, i)

    def text_changed(self, text):
        """Called when text is edited"""
        pass 

    def getvalue(self):
        return unicode(self.currentText())
        
# class DBCompleter(QtGui.QCompleter):
#     def __init__(self, parent=None, choices=None):
#         """Customized QCompleter for DB fields"""
#         
#         choices = choices or ["one","two","three"]
#         super(DBCompleter, self).__init__(parent=parent)

#####################
# Base pages
#####################

class Page(QtGui.QWizardPage):
    pagename = None
    rectype = None
    rectypes = []
    base_ui = emdash.ui.Ui_Wizard.Ui_Wizard
    helptext = None
    title = "Wizard"
    
    def __init__(self, parent=None, title=None, helptext=None):
        """Base Page used in Session Wizards"""
        super(Page, self).__init__(parent)
        self.p = parent
        self.updated = False
        
        if self.base_ui != None:
            self.ui = self.base_ui()
        if self.ui:
            self.ui.setupUi(self)        

        if helptext:
            self.helptext = helptext
        if self.helptext:
            self.ui.label_help.setText(self.helptext)                
            
        if title:
            self.title = title        
        if self.title:
            self.setTitle(self.title)
        else:
            self.setTitle("%s"%self.rectype)

        self.setupUi()
        self.init()

    def init(self):
        pass

    def setupUi(self):
        """Override to modify Qt Designer-based UIs"""
        pass
        
    def setlabels(self):
        """Set some labels at initializePage time"""
        pass

    def update(self):
        """Update form based on Wizard parent state"""
        pass

    def getvalue(self):
        """Return a selected record or entered record"""
        return None

    def initializePage(self):
        """Called when a Page is shown, usually calls self.update()"""
        self.update()
        self.setlabels()        
        
    def getroot(self):
        """Get root value from parent Wizard"""
        return self.p.results_select.get("project") or self.p.results_select.get("root")
        
    def getbody(self):
        return """Text goes here"""

#####################
# Second level pages
#####################
        
class PageRectypeSelect(Page):
    base_ui = emdash.ui.Ui_Wizard_rectype.Ui_Wizard_rectype
    title = "Select one of the following Protocols to Continue"

    def setupUi(self):        
        body = self.getbody()
        rds = emdash.config.db().recorddef.get(self.rectypes)
        self.radios = {}
        for rd in rds:
            radio = QtGui.QRadioButton()
            
            rdtext = rd.get('name')
            if rd.get('desc_short') not in [None, "None", ""]:
                rdtext = "%s (%s)"%(rd.get('desc_short'), rd.get('name'))            
            radio.setText(rdtext)
            # radio.setDown(True)
            self.ui.layout.addWidget(radio)
            self.radios[rd.get('name')] = radio

    def validatePage(self):
        v = self.getvalue()
        if v != None:
            return True
        error('You must make a selection.')
        return False

    def getvalue(self):
        for k,v in self.radios.items():
            if v.isChecked():
                return k
        
class PageText(Page):
    """Simple Text Page"""
    
    def setupUi(self):        
        body = self.getbody()        
        label = QtGui.QLabel(body)
        label.setWordWrap(True)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)

### Base New Page         

class PageNew(Page):
    base_ui = emdash.ui.Ui_Wizard_New.Ui_Wizard_New    
    map_pd_elements = {}
    ignore_params = ['date_start', 'date_end', 'performed_by']
    
    def process_markdown(self, view):
        # The views are in Markdown, 
        # but it doesn't work quite right in this Qt form, 
        # so do some simple markdown processing    
        ret = []
        for t in [i.strip() for i in view.split("\n")]:
            e = 'p'
            if t.startswith("###"):
                e = 'h3'
                t = t[3:]
            elif t.startswith('##'):
                e = 'h3'
                t = t[2:]
            elif t.startswith('#'):
                e = 'h1'
                t = t[1:]
            t = t.strip()
            if t:
                ret.append('<%s>%s</%s>'%(e, t, e))
        return "".join(ret)
        
    def update(self):
        """Create a reasonable form based on the record 
        definition "simpleform" view."""
        
        if self.updated:
            return            
        self.updated = True
        
        # rec..
        rec = {}
        if self.p.results_select.get(self.rectype) >= 0:
            rec = emdash.config.db().record.get(self.p.results_select.get(self.rectype))
                
        self.map_pd_elements = {}
        name = emdash.config.db().auth.check.context()[0]
        rd = emdash.config.db().recorddef.get(self.rectype)
        tview = rd.get("views").get("simpleform") or rd.get("mainview") or ''

        pds = []
        parsed = []

        regex = re.compile(VIEW_REGEX)
        for match in regex.finditer(tview):
            if match.group('type') in ['*', '$']:
                pds.append(match.group("name"))

        pds = emdash.config.db().paramdef.get(pds)
        pds = dict([[i.get('name'), i] for i in pds])

        #########

        # outer = QtGui.QVBoxLayout(self)
        scroll = QtGui.QScrollArea()
        scroll.setMinimumWidth(400)
        self.ui.layout.addWidget(scroll)
        
        fq = QtGui.QWidget()
        scroll.setWidget(fq)
        
        f = QtGui.QFormLayout(fq)
        f.setSizeConstraint(QtGui.QLayout.SetFixedSize)

        for match in regex.finditer(tview):
            if match.group('type') in ['*', '$']:
                k = match.group('name')
                defaultunits = pds.get(k).get("defaultunits")
                label = QtGui.QLabel()
                if defaultunits:
                    label.setText("%s (%s)"%(
                        pds.get(k).get("desc_short"), 
                        defaultunits))    
                else:
                    label.setText(pds.get(k).get("desc_short"))

                if pds.get(k).get('name') in self.ignore_params:
                    continue
                
                w = edititem(
                    parent=self, 
                    pd=pds.get(k), 
                    value=rec.get(k), 
                    name=name)
                self.map_pd_elements[k] = w            
                f.addRow(label, w)

            elif match.group('text'):
                t = self.process_markdown(match.group('text'))
                if t:
                    label = QtGui.QLabel()
                    label.setTextFormat(QtCore.Qt.RichText)
                    label.setText(t)
                    label.setWordWrap(True)
                    f.addRow(label)

    def getvalue(self):
        """Create a properly initialized record based 
        on the results in the page"""        
        
        project = self.p.results_select.get("project")
        print "PROJECT:", project
        if project:
            rec = emdash.config.db().record.new(rectype=self.rectype, inherit=[project])
        else:
            rec = emdash.config.db().record.new(rectype=self.rectype)
                
        # qstring's don't go through xmlrpc well on windows..?
        for k,v in self.map_pd_elements.items():
            rec[unicode(k)] = unicode(v.getvalue())
        if not rec.get("parents"): rec["parents"] = []
        if not rec.get("children"): rec["children"] = []
        return rec

    def validatePage(self):
        """Validate the record"""        
        rec = self.getvalue()
        try:
            emdash.config.db().record.validate(rec)
            return True
        except Exception, e:
            error('Could not validate form: %s'%e)
            return False
            
class PageEdit(PageNew):
    def getvalue(self):    
        rec = {}
        for k,v in self.map_pd_elements.items():
            rec[unicode(k)] = unicode(v.getvalue())            
        return rec

### Base Record Selecting pages        

class PageSelect(Page):                
    """Base class for Pages that Select records"""
    rectype = None
    rectypes = []
    accepted = []
    base_ui = emdash.ui.Ui_Wizard_Existing.Ui_Wizard_Existing
    recurse = -1
    expand = -1
    
    def check_radio_existing(self):
        self.ui.radio_existing.setChecked(True)    

    def update(self):
        """Update list of records to show"""
        root = self.getroot()
        emdash.log.msg("Root:", root)

        # Backwards compat.         
        self.rectypes = [i.get('name') for i in emdash.config.db().recorddef.get(self.rectypes)]
        self.accepted = [i.get('name') for i in emdash.config.db().recorddef.get(self.accepted)]        

        recnames, paths, roots = emdash.config.db().record.findpaths(
            None,
            ['group'],
            ['project*']
            )

        m = emdash.emmodels.RecordTreeModel(
            root=root, 
            recnames=recnames, 
            paths=paths, 
            parent=self, 
            recurse=self.recurse)        

        self.ui.tree_records.setModel(m)
        self.ui.tree_records.collapseAll()
        if self.expand == -1:
            self.ui.tree_records.expandAll()
        elif self.expand > 0:
            self.ui.tree_records.expandToDepth(self.expand-1)

        self.connect(
            self.ui.tree_records, 
            QtCore.SIGNAL("clicked(QModelIndex)"), 
            self.check_radio_existing)
    
    def getvalue_tree(self):
        """Get value from record list"""
        ind = self.ui.tree_records.currentIndex()
        model = ind.model()
        if ind and model:
            name = ind.model().index(ind.row(), 1, ind.parent()).data().toString()
            recname = ind.data().toString()
            return name
        else:
            return None
    
    def getvalue(self):
        """Get value from radio buttons or record list"""
        return self.getvalue_tree()
            
    def validatePage(self):
        rec = self.getvalue()
        if rec >= 0:
            rec = emdash.config.db().record.get(rec)
            if self.accepted and rec.get("rectype") not in self.accepted:
                t = """Record %s is not a valid protocol for this page (%s).
                Accepted protocols are: %s
                """%(
                    rec.get("name"), 
                    rec.get("rectype"), 
                    ", ".join(self.accepted))
                error(t)
                return False
        elif rec < -2:
            t = """You must select a record to continue. 
            Accepted protocols are: %s"""%", ".join(self.accepted)
            error(t)
            return False
                        
        return True

class PageExisting(PageSelect):
    """Select an existing page"""

    def setlabels(self):
        if not self.title:
            self.setTitle("Select Existing %s"%self.rectype)    

class PageNewOrExisting(PageSelect):
    """Select an existing page, or create a new page"""
    
    def setupUi(self):
        self.ui.radio_new = QtGui.QRadioButton()
        self.ui.radio_new.setText("New %s"%self.rectype)
        self.ui.radio_new.setChecked(True)
        self.ui.layout.addWidget(self.ui.radio_new)
        
    def setlabels(self):
        self.ui.radio_new.setText("New %s"%self.rectype)
        self.ui.radio_existing.setText("Existing %s"%self.rectype)
        if not self.title:
            self.setTitle("Select %s for this grid"%self.rectype)

    def getvalue(self):
        if self.ui.radio_new.isChecked():
            return -1
        return self.getvalue_tree()
        
class PageNewOrExistingSkip(PageSelect):
    """Select an existing page, or create a new page, 
    or skip this for now..."""

    def setupUi(self):
        self.ui.radio_skip = QtGui.QRadioButton()
        self.ui.radio_skip.setText("Skip this step")
        self.ui.radio_new = QtGui.QRadioButton()
        self.ui.radio_new.setText("New %s"%self.rectype)
        self.ui.radio_new.setDown(True)
        self.ui.layout.addWidget(self.ui.radio_skip)
        self.ui.layout.addWidget(self.ui.radio_new)

    def setlabels(self):
        self.ui.radio_new.setText("New %s"%self.rectype)
        self.ui.radio_existing.setText("Existing %s"%self.rectype)
        self.setTitle("%s for this grid"%self.rectype)    

    def getvalue(self):
        if self.ui.radio_skip.isChecked():
            return -2
        if self.ui.radio_new.isChecked():
            return -1
        return self.getvalue_tree()
        
class PageExistingOrSkip(PageSelect):
    """Select an existing page, or create a new page,
    or skip this for now..."""

    def setupUi(self):
        self.ui.radio_skip = QtGui.QRadioButton()
        t = "Skip this step; I am ABSOLUTELY SURE that it is not required!"
        self.ui.radio_skip.setText(t)
        self.ui.layout.addWidget(self.ui.radio_skip)

    def getvalue(self):
        if self.ui.radio_skip.isChecked():
            return -2
        return self.getvalue_tree()

####################
# Specific pages
####################

class PageStart(PageText):
    pagename = "start"
    def getbody(self):
        return "This wizard will assist in starting a grid imaging session"

class PageRectypeSelect_freezing(PageRectypeSelect):
    rectypes = ["freezing*"]
    pagename = "rectype_freezing"
    title = "Select one of the following freezing session types to continue"

class PageSelect_any(PageExisting):
    pagename = '_any'
    recurse = 3
    expand = 0
    title = "Select a Record"
    
class PageSelect_project(PageExisting):
    pagename = "project"
    rectype = "project"
    rectypes = ["project*"]
    accepted = ["project*"]
    recurse = 5
    expand = 1
    title = "Select a destination"

    def getroot(self):
         return self.p.results_select.get("root")        
        
    def setlabels(self):
        t = "Use a destination from this list"
        self.ui.radio_existing.setText(t)

# PageSelect_microscopy
class PageSelect_microscopy(PageExisting):
    pagename = "microscopy"
    rectype = "microscopy"
    rectypes = ["microscopy*"]
    accepted = ["microscopy*"]
    recurse = 1
    expand = 0
    title = "Select a Microscopy Session"

    def getroot(self):
        microscope = self.p.results_select.get("microscope")
        return microscope
        
    def setlabels(self):
        t = "Use a destination from this list"
        self.ui.radio_existing.setText(t)
        
class PageSelect_grid_imaging(PageNewOrExisting):
    pagename = "grid_imaging"
    rectype = "grid_imaging"
    rectypes = ["grid_imaging"]
    accepted = ["grid_imaging"]
    title = "Select a Grid Imaging Session"    

    def setlabels(self):
        self.ui.radio_existing.setText("Use a grid from this list")

class PageSelect_grid_preparation(PageNewOrExisting):
    pagename = "grid_preparation"
    rectype = "grid_preparation"
    rectypes = ["grid_preparation"]
    accepted = ["grid_preparation"]
    title = "New Grid > Select Grid Preparation"    
    helptext = """A Grid Preparation record should be created for every 
    grid that is prepared. It contains details about grid type and batch ID,
    substrate, mesh and hole size, pre- and post-freezing treatment such as
    plasma cleaning. It should also be linked to a Freezing Session,
    which contains detailed information about the freezing device and what
    settings were used. In this screen, you can select an existing Grid
    Preparation (for instance, a grid that was prepared and then stored for
    later use) or create a new Grid Preparation record."""
        
    def setlabels(self):
        self.ui.radio_existing.setText("Use a grid from this list")

class PageSelect_freezing(PageExistingOrSkip):
    pagename = "freezing"
    rectype = "freezing"
    rectypes = ["freezing*"]
    accepted = ["freezing*"]
    title = "New Grid > Select a Freezing Session"    
    helptext = """Each frozen grid must be linked to a Freezing Session
    record. You should only skip this screen if it is not applicable because
    the grid was not frozen (e.g. magnification calibration.) 
    If you have not created the Freezing Session for this grid, you should
    exit this wizard and run the 'New Freezing Session' wizard first, to
    ensure the workflow is complete."""

    def setlabels(self):
        self.ui.radio_existing.setText("Use a freezing session from this list")

class PageSelect_aliquot(PageNewOrExisting):
    pagename = "aliquot"
    rectype = "aliquot"
    rectypes = ["aliquot"]
    accepted = ["aliquot"]
    title = "New Freezing Session > Select Aliquot"
    helptext = """Select the aliquot that was used for this Freezing Session. 
    The aliquot should be linked to a Purification record. This record helps
    keep track of the exact storage location and aliquot batch for each
    Freezing Session."""
    
    def setlabels(self):
        self.ui.radio_existing.setText("Use an aliquot from this list")
        self.ui.radio_new.setText("Create a new aliquot")

class PageSelect_purification(PageNewOrExisting):
    pagename = "purification"
    rectype = "purification"
    rectypes = ["purification"]
    accepted = ["purification"]
    title = "New Freezing Session > New Aliquot > Select Purification"
    helptext = """Select the Purification that was the 
    source for this aliquot."""

    def setlabels(self):
        self.ui.radio_existing.setText("Use a purification from this list")
        self.ui.radio_new.setText("Create a new purification")

class PageMiddle(PageText):
    pagename = "middle"
    title = "New Grid > Create Records"

    def getbody(self):
        return """You will now create the requested records. 
        You may press back to make any changes before committing."""

class PageNew_grid_imaging(PageNew):
    pagename = "new_grid_imaging"
    rectype = "grid_imaging"
    title = "New Grid > Grid Imaging Details"    
    helptext = """Please describe the purpose of this this Imaging Session; 
    it will help you and your collaborators find your images in the future.
    The 'default' parameters below will set the initial values for images
    collected during this session. During the session, you can adjust the
    sliders/input fields to change the parameters applied to uploaded images.
    After an image is uploaded (the status column will contain a Record ID)
    you can click on the values in each column to adjust a value for a 
    single image."""

class PageEdit_microscopy(PageEdit):
    pagename = "edit_microscopy"
    title = "Microscopy Details"    

    def init(self):
        self.rectype = emdash.config.get('session_protocol')
        self.helptext = """Please enter the microscope settings for this
        session, as well as the general purpose/goal for this session.
        """

class PageNew_microscopy(PageNew):
    pagename = "edit_microscopy"
    title = "Microscopy Details"
    
    def init(self):
        self.rectype = emdash.config.get('session_protocol')
        self.helptext = """Please enter the microscope settings for this
        session, as well as the general purpose/goal for this session.
        """

class PageEdit_grid_imaging(PageEdit):
    pagename = "edit_grid_imaging"
    rectype = "grid_imaging"
    title = "New Grid > Edit Grid Imaging Details"    
    helptext = """You can change the purpose or other details of this 
    Imaging Session."""

class PageNew_grid_preparation(PageNew):
    pagename = "new_grid_preparation"
    rectype = "grid_preparation"
    title = "New Grid > New Grid Prep"        
    helptext = """Please enter the Grid Preparation details for this grid. 
    You may leave the vitrobot-related parameters empty if they are specified
    in the parent Freezing Session. Please make sure to describe any pre- or
    post-freezing treatments you applied to the grid."""

class PageNew_purification(PageNew):
    pagename = "new_purification"
    rectype = "purification"
    title = "New Freezing Session > New Purification"    
    helptext = "Create a new Purification."

class PageNew_aliquot(PageNew):
    pagename = "new_aliquot"
    rectype = "aliquot"
    title = "New Freezing Session > New Aliquot"
    helptext = "Create a new Aliquot."

class PageNew_freezing(PageNew):
    pagename = "new_freezing"
    rectype = "freezing_vitrobot"
    title = "New Freezing Session > Freezing Session Details"
    helptext = """Enter the details for this Freezing Session. If different
     settings were used for each grid frozen in this session, enter the
     default settings, then make sure to fill in the freezing settings in each
     Grid Preparation record."""

class PageCommit(Page):
    pagename = "commit"
    title = "Grid Wizard > Commit"
    ui = None
        
    def setupUi(self):
        self.setCommitPage(True)
        body = "Press finish to save changes and complete this Wizard."            
        label = QtGui.QLabel(body)
        layout = self.layout()
        layout.addWidget(label)
        
####################
# Wizard
####################

class SessionWizard(QtGui.QWizard):
    """Wizard for creating a grid_imaging session"""
    signal_done = QtCore.pyqtSignal(object, object)        
        
    def __init__(self, parent=None, selected=None):
        super(SessionWizard, self).__init__(parent)
        
        # Results..
        self.results_select = {"root": "0"}
        if selected:
            self.results_select.update(selected)
                                                
        self.results_new = {}
        self.results_text = {"root":"Root Record"}        
        self.newrecords = None                        
        # Setup pages..
        self.pages = []        
        self.lookup_skip = {}
        self.lookup_new = {}
        self.lookup_found = {}
        self.lookup_rectype = {}
        self.makepages()
        # Insert the pages into Qt Wizards
        self.pagesbyid = {}
        self.pagenames = {}
        for count, i in enumerate(self.pages):
            self.addPage(i)
            self.pagesbyid[count] = i
            self.pagenames[i.pagename] = count            
            
        self.setWizardStyle(QtGui.QWizard.ClassicStyle)
        self.resize(800,700)

    def makepages(self):
        pass
        
    def accept(self):
        try:
            self.signal_done.emit(*self.getrecords())
            self.done(0)
        except Exception, e:
            error(e)
        
    def nextId(self):    
        """Logic for Session Wizard. Based on current wizard state, 
        returns next page to show."""
        # This of course is VERY UGLY and HACKY, since it relies on
        #  complicated lookup tables and return values to
        # flow from page to page. But this was better than writing my own
        #  Wizard management system; going through
        # these hoops to use the Qt Wizard system provides alot of tricky
        #  functionality that would be painful
        # to implement on my own.
        cid = self.currentId()
        page = self.currentPage()
        pages = self.pageIds()            
        r = page.getvalue()
        next = cid + 1
        
        if isinstance(page, (PageNew, PageEdit)):
            # print "This is a new record page. Did we get the record? ", page
            next = cid + 1
            self.results_new[page.pagename] = r

        elif isinstance(page, PageRectypeSelect):
            if r == None:
                next = cid
            else:
                p = self.pagesbyid.get(self.pagenames.get(
                    self.lookup_rectype.get(page.pagename)))
                p.rectype = r

        elif isinstance(page, PageSelect):
            #print "This is a select page! ", page
            if r == None:
                #print "Page %s: Did not get value for %s! 
                # Staying at page %s"%(cid, page.rectype, cid) 
                next = cid
            elif r == -2:
                next = self.pagenames.get(self.lookup_skip.get(page.pagename))
                #print "Page %s: Got skip for %s, 
                # skipping to end"%(cid, page.rectype)
            elif r == -1:
                next = self.pagenames.get(self.lookup_new.get(page.pagename))
                #print "Page %s: Got new for %s, 
                # going to %s"%(cid, page.rectype, next)
                if next == None:
                    next = cid + 1
            elif r >= 0:
                next = self.pagenames.get(
                    self.lookup_found.get(page.pagename))
                #print "Page %s: Found record %s for %s, 
                # going to %s"%(cid, r, page.rectype, next)
                if next == None:
                    next = cid + 1
            else:
                raise Exception, "Invalid response"
            self.results_select[page.pagename] = r            
        
        elif isinstance(page, PageText):
            # print "Page %s: non-interactive, going to %s"%(cid,cid+1)        
            next = cid + 1
        
        elif isinstance(page, PageCommit):
            # print "Page commit"
            pass
                
        if cid == pages[-1]:
            next = -1

        if next == None:
            next = cid

        return next

    ###################################
    # Ok, actually create sessions
    ###################################
    
    def getrecords(self):
        s = self.results_select
        n = self.results_new
                
        records = {}
        found = {}
        return records, found

class SelectAnyWizard(SessionWizard):
    signal_any = QtCore.pyqtSignal(unicode)
    
    def makepages(self):
        self.pages = [
            PageSelect_project(parent=self),
            PageSelect_any(parent=self),
            PageCommit(parent=self)
        ]
        
    def accept(self):
        try:
            # self.signal_done.emit(*self.getrecords())
            target = self.results_select.get('_any')
            self.signal_any.emit(target)
            self.done(0)
        except Exception, e:
            error(e)

class EditMicroscopyWizard(SessionWizard):
    def makepages(self):
        self.pages = [PageEdit_microscopy(parent=self)]
        
    def getrecords(self):        
        s = self.results_select
        page = self.currentPage()            
        microscopy = s.get("microscopy")
        rec = {'name':microscopy}
        for k,v in page.getvalue().items():
            if v:
                rec[k]=v
        return [rec], {}

class NewMicroscopyWizard(SessionWizard):
    def makepages(self):
        self.pages = [PageNew_microscopy(parent=self)]

    def getrecords(self):
        s = self.results_select
        page = self.currentPage()            
        microscopy = s.get("microscopy")
        rec = {'name':microscopy}
        for k,v in page.getvalue().items():
            if v:
                rec[k]=v
        return [rec], {}

class EditGridImagingWizard(SessionWizard):
    def makepages(self):
        self.pages = [PageEdit_grid_imaging(parent=self)]
        
    def getrecords(self):        
        s = self.results_select
        page = self.currentPage()            
        microscopy = s.get("grid_imaging")
        rec = {'name':microscopy}
        for k,v in page.getvalue().items():
            if v:
                rec[k]=v
        return [rec], {}

class NewGridWizard(SessionWizard):
    def makepages(self):
        """Setup the order of the wizard and page choices"""        
        self.pages = [
            PageSelect_project(parent=self),
            PageSelect_grid_preparation(parent=self),
            PageSelect_freezing(parent=self),    
            PageNew_grid_preparation(parent=self),
            PageNew_grid_imaging(parent=self),
            PageCommit(parent=self)
        ]        
        self.lookup_new = {
            "grid_preparation": "freezing"
        }        
        self.lookup_found = {
            "subproject": "grid_preparation",
            "freezing": "new_grid_preparation",
            "grid_preparation": "new_grid_imaging"
        }        
        self.lookup_skip = {
            "freezing": "new_grid_preparation"
        }
        
    def getrecords(self):        
        s = self.results_select
        n = self.results_new
        records = {}
        records["-1"] = n.get("new_grid_imaging")
        records["-1"]["date_occurred"] = emdash.config.gettime()
        records["-1"]["performed_by"] = emdash.config.db().auth.check.context()[0]
        
        # -1 is GRID_IMAGING
        # -2 is GRID_PREPARATION
        # Add link to the PROJECT
        records["-1"]["parents"].append(s.get("project"))
        # Add link to the MICROSCOPY
        if s.get("microscopy") >= 0:
            records["-1"]["parents"].append(s.get("microscopy"))
        if s.get("grid_preparation") >= 0:
            # If we're linking to an EXISTING GRID_PREPARATION
            records["-1"]["parents"].append(s.get("grid_preparation"))
        elif n.get("new_grid_preparation"):
            # Otherwise, add NEW GRID_PREPARATION
            records["-2"] = n.get("new_grid_preparation")

            # Decide what parents to use below...
            records["-2"]['parents'] = []

            if s.get('freezing') >= 0:
                # Link to an EXISTING FREEZING
                records["-2"]['parents'].append(s.get("freezing"))
            else:
                # Otherwise, comment that no freezing session was specified
                records["-2"]["parents"].append(s.get("project"))
                records["-2"]['comments'] = 'No parent freezing session was specified when this record was created.'    
            
            # Add the new grid prep as a parent
            # ... IMPORTANT: Bug workaround. Add the grid_imaging back as a child.
            records["-2"]["children"].append("-1")
            records["-1"]["parents"].append("-2")

        for k in records:
            records[k]["name"] = k
            
        found = {}
        for k,v in s.items():
            if v >= 0:
                found[k] = v    
        return records.values(), found
        
class NewGridSimpleWizard(SessionWizard):
    def makepages(self):
        """Setup the order of the wizard and page choices"""        
        self.pages = [
            PageSelect_project(parent=self),
            PageNew_grid_imaging(parent=self),
            PageCommit(parent=self)
        ]
        self.lookup_found = {
            "subproject": "new_grid_imaging"
        }
        
    def getrecords(self):        
        s = self.results_select
        n = self.results_new
        records = {}
        records["-1"] = n.get("new_grid_imaging")
        records["-1"]["date_occurred"] = emdash.config.gettime()
        records["-1"]["performed_by"] = emdash.config.db().auth.check.context()[0]
        # Add link to the PROJECT
        records["-1"]["parents"].append(s.get("project"))
        # Add link to the MICROSCOPY
        if s.get("microscopy") >= 0:
            records["-1"]["parents"].append(s.get("microscopy"))
        for k in records:
            records[k]["name"] = k
        found = {}
        for k,v in s.items():
            if v >= 0:
                found[k] = v    
        return records.values(), found

class NewFreezingWizard(SessionWizard):
    def makepages(self):
        """Setup the order of the wizard and page choices"""
        self.pages = [
            PageSelect_project(parent=self),
            PageRectypeSelect_freezing(parent=self),
            PageSelect_aliquot(parent=self),
            PageSelect_purification(parent=self),
            PageNew_purification(parent=self),
            PageNew_aliquot(parent=self),
            PageNew_freezing(parent=self),
            PageCommit(parent=self)
        ]

        self.lookup_rectype = {
            "rectype_freezing": "new_freezing"
        }

        self.lookup_new = {
            "aliquot": "purification",
            "purification": "new_purification"
        }

        self.lookup_found = {
            "aliquot": "new_freezing",
            "purification": "new_aliquot"
        }

    def getrecords(self):        
        s = self.results_select
        n = self.results_new
        # Create the freezing record
        records = {}
        records["-1"] = n.get('new_freezing')
        records["-1"]['date_occurred'] = emdash.config.gettime()
        records["-1"]['performed_by'] = emdash.config.db().auth.check.context()[0]

        # Reset the parents; we'll decide what to do below
        records["-1"]['parents'] = []
        
        # -1 is FREEZING
        # -2 is ALIQUOT
        # -3 is PURIFICATION
        if s.get('aliquot') >= 0:
            # Set parents for FREEZING to an EXISTING ALIQUOT
            records["-1"]['parents'] = [s.get('aliquot')]
        
        elif n.get('new_aliquot'):
            # Create a NEW ALIQUOT
            records["-2"] = n.get('new_aliquot')
            # in this case, FREEZING is not linked to project, but to NEW ALIQUOT
            records["-2"]['children'] = ["-1"]
            records["-1"]['parents'] = ["-2"] 
            # Now... what parent does the NEW ALIQUOT have?
            if s.get('purification') >= 0:
                # Set parents for NEW ALIQUOT to an EXISTING PURIFICATION
                records["-2"]['parents'] = [s.get('purification')]
            elif n.get('new_purification'):
                # Create a NEW PURIFICATION
                records["-3"] = n.get('new_purification')
                # Link the NEW PURIFICATION to the project
                records["-3"]['parents'].append(s.get('project'))
                # Set the NEW PURIFICATION to the parent of NEW ALIQUOT
                records["-3"]['children'] = ["-2"]
                records["-2"]['parents'] = ["-3"]                
            else:
                emdash.log.error("Aliquot without parent purification?? Please report this.")
                records["-2"]['parents'] = [s.get('project')]
                records["-2"]['comments'] = 'This record is linked to the project because no parent purification was specified.'            
        else:
            records["-1"]['parents'] = [s.get('project')]
            records["-1"]['comments'] = "This record is linked to the project because no parent aliquot was specified."


        for k in records:
            records[k]["name"] = k

        found = {}
        return records.values(), found
        
class NewAliquotWizard(SessionWizard):
    pass

# class SelectGridWizard(SessionWizard):
#     def makepages(self):
#         """Setup the order of the wizard and page choices"""
#         self.pages = [
#             PageSelect_project(parent=self),
#             PageSelect_grid_imaging(parent=self),
#             PageCommit(parent=self)            
#         ]
# 
#     def getrecords(self):        
#         s = self.results_select
#         found = {}
#         for k,v in s.items():
#             if v >= 0:
#                 found[k] = v    
#         return [], found                

class SelectGridWizard(SessionWizard):
    def makepages(self):
        """Setup the order of the wizard and page choices"""
        self.pages = [
            PageSelect_project(parent=self),
            PageSelect_grid_imaging(parent=self),
            PageCommit(parent=self)            
        ]

    def getrecords(self):        
        s = self.results_select
        found = {}
        for k,v in s.items():
            if v >= 0:
                found[k] = v    
        return found.get('grid_imaging')
            
# if __name__ == '__main__':
#     app = QtGui.QApplication(sys.argv)
#     wizard = NewFreezingWizard()
#     wizard.show()
#     sys.exit(app.exec_())
    