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
import emdash.upload

################################
# Microscope Upload
################################

class MicroscopeUpload(emdash.upload.BaseUpload):

    ui = emdash.ui.Ui_MicroscopeUpload.Ui_Upload
    headers = ["_recname", "tem_magnification_set", "ctf_defocus_set", 'tem_dose_rate', 'time_exposure_tem', "assess_image_quality", "_status"]
    headernames = ["Name", "Mag", "Defocus", "Dose", "Exposure", "Quality", "Status"]
    headerwidths = [250, 60, 60, 60, 60, 80, 50]

    def init(self):
        # Defaults..
        self.ui.button_path.addAction(QtGui.QAction("Select directory", self, triggered=self._set_path))        
        # self.ui.button_path.addAction(QtGui.QAction("Select directory -- new files only", self, triggered=self._set_path_newonly))
        self.ui.button_path.addAction(QtGui.QAction("Add files", self, triggered=self._add_files))

        # Comments
        self.ui.button_addcomment.addAction(QtGui.QAction("this grid", self, triggered=functools.partial(self.addcomment, rectype='grid_imaging')))
        self.ui.button_addcomment.addAction(QtGui.QAction("this microscopy session", self, triggered=functools.partial(self.addcomment, rectype='microscopy')))
        self.ui.button_addcomment.addAction(QtGui.QAction("this microscope", self, triggered=functools.partial(self.addcomment, rectype='microscope')))            
    
        # More Drop-down buttons
        self.ui.button_grid.addAction(QtGui.QAction("New grid imaging session", self, triggered=self._newgrid_wizard))
        # self.ui.button_grid.addAction(QtGui.QAction("New grid imaging session (no grid prep or freezing)", self, triggered=self._newgrid_simple_wizard))
        self.ui.button_grid.addAction(QtGui.QAction("New freezing session", self, triggered=self._newfreezing_wizard))
        # self.ui.button_grid.addAction(QtGui.QAction("Edit grid imaging session details", self, triggered=self._edit_grid_wizard))
        self.ui.button_grid.addAction(QtGui.QAction("Browse for existing grid imaging session", self, triggered=self._select_grid_wizard))

        self.ui.button_grid.addAction(QtGui.QAction("Browse for destination", self, triggered=self._select_target_wizard))
        self.ui.button_grid.addAction(QtGui.QAction("Manually select destination", self, triggered=self._name_target_wizard))

        # Session
        self.ui.button_session.addAction(QtGui.QAction("Select existing session", self, triggered=self._name_microscopy_wizard))        

        # New Micrograph
        # self.ui.button_newmicrograph.clicked.connect(self.newmicrograph, type=QtCore.Qt.QueuedConnection)            
    
        # Editables
        self.connect_slider('tem_magnification_set', factor=1.0)
        self.connect_slider('ctf_defocus_set')
        self.connect_slider('tem_dose_rate')
        self.connect_slider('time_exposure_tem')
        
        self.ui.edit_id_micrograph.textChanged.connect(functools.partial(self.set_setting, param='id_micrograph'), type=QtCore.Qt.QueuedConnection)
        self.ui.button_assess_ice_comments.clicked.connect(self._assess_ice_comments, type=QtCore.Qt.QueuedConnection)
        self.ui.button_assess_ice_thick.clicked.connect(self._assess_ice_thick, type=QtCore.Qt.QueuedConnection)

        self.ui.tree_files.star_column(len(self.headers)-2)

    def _check_target(self):
        # Set the target if a wizard returns a grid_imaging record...        
        grid = self.names.get('grid_imaging')
        if grid is not None:
            self.set_target(grid)

    @QtCore.pyqtSlot()
    def login_cb(self):
        # This wizard will call begin_Session
        self.update_ui()
        self.show()
        self._newmicroscopy_wizard()

    @QtCore.pyqtSlot()
    def update_ui(self):
        super(MicroscopeUpload, self).update_ui()

        self.ui.frame_settings.setEnabled(self.ui.button_path.isEnabled())
        self.ui.button_newmicrograph.setEnabled(self.ui.button_path.isEnabled())
    
        # Update the UI to reflect these selected records
        self.ui.label_project.setText(self.getlabel(rectypes=["project", "subproject"]))
        self.ui.label_freeze.setText(self.getlabel(rectypes=["grid_preparation"]))
    
        gir = self.recs.get(self.target, dict())
        if gir.get('tem_magnification_set') != None:
            self.ui.edit_tem_magnification_set.setText(str(gir.get('tem_magnification_set')))
        if gir.get('ctf_defocus_set') != None:
            self.ui.edit_ctf_defocus_set.setText(str(gir.get('ctf_defocus_set')))
        if gir.get('time_exposure_tem') != None:
            self.ui.edit_time_exposure_tem.setText(str(gir.get('time_exposure_tem')))
        if gir.get('tem_dose_rate') != None:
            self.ui.edit_tem_dose_rate.setText(str(gir.get('tem_dose_rate')))    
    
        film_type = self.recs.get(self.names.get(emdash.config.get('session_protocol')), dict()).get('film_type', '')
        if film_type.lower() in emdash.config.get('film_types'):
            self.ui.edit_id_micrograph.show()
            self.ui.label_newmicrograph.show()
            self.ui.button_newmicrograph.show()            
        else:
            self.ui.edit_id_micrograph.hide()
            self.ui.label_newmicrograph.hide()
            self.ui.button_newmicrograph.hide()

    def update_comments(self):
        root = self.names.get('microscope')
        if  root == None:
            return
        
        coms = []
        try:    
            recs = emdash.config.db().rel.children(self.names["microscope"], recurse=1, rectype=["microscopy*"])
            coms = emdash.config.db().record.findcomments(recs)            
        except:
            pass
    
        # update the recnames..
        try:
            self.recnames.update(emdash.config.db().record.render([i[0] for i in coms]))
        except:
            pass
    
        html = []    
        for c in sorted(coms, key=lambda x:x[2], reverse=True):
            t = """<a href="%s/record/%s/?ctxid=%s">%s</a>: %s @ %s: <br /> %s <br /><br />"""%(emdash.config.get('host'), c[0], emdash.config.get('ctxid'), self.recnames.get(str(c[0]), c[0]), c[1], c[2], c[3])
            html.append(t)
            
        self.ui.browser_comments.setHtml("".join(html))
        
        # Update...
        self.ui.edit_addcomment.clear()
        self.ui.button_addcomment.setEnabled(True)
        self.ui.edit_addcomment.setEnabled(True)
    
    
    ##################################
    # Microscope session management
    ##################################
    
    @QtCore.pyqtSlot(object, object)
    def begin_session(self, editrecords, selectrecords):    
        # Find the correct microscope
        t = emdash.config.db().time.now()
        if emdash.config.get('microscope') == None:
            raise ValueError, "No microscope specified!"
    
        childrecs = set(emdash.config.db().rel.children(emdash.config.get('microscope'), recurse=1, rectype="microscope"))
        childrecs.add(emdash.config.get('microscope'))
        microscopes = emdash.config.db().record.get(list(childrecs))
        microscope = None
    
        emdash.log.msg("Looking for microscope configuration for today's date:", t)
    
        for m in microscopes:
            if m.get('date_start') <= t < m.get('date_end'):
                emdash.log.msg("Using microscope configuration:", m.get('name'))
                self.names['microscope'] = m.get('name')
    
        if not self.names.get('microscope'):
            self.names['microscope'] = emdash.config.get('microscope', 0)
            emdash.log.msg("Warning: No microscope configuration specified for today's date: %s... using %s as session parent"%(t, self.names['microscope']))
    
        # Use an existing session, or create a new one.
        if selectrecords.get(emdash.config.get('session_protocol')):
            rec = emdash.config.db().record.get(selectrecords.get(emdash.config.get('session_protocol')))
    
        else:
            # Copy microscopy permissions and link to microscopy
            m = emdash.config.db().record.get(self.names.get('microscope'))
            rec = editrecords[0]
            rec['parents'] = m['name']
            rec['groups'] = m['groups']
            rec['permissions'] = m['permissions']
            rec["date_start"] = emdash.config.gettime()
            rec = emdash.config.db().record.put(rec)
    
        # Update the targets
        self.names[emdash.config.get('session_protocol')] = rec.get("name")
        self.update_comments()

        # ... start the session
        super(MicroscopeUpload, self).begin_session()
    
    @QtCore.pyqtSlot()
    def end_session(self):
        if self.names.get(emdash.config.get('session_protocol')) != None:
            try:
                rec = emdash.config.db().record.get(self.names.get(emdash.config.get('session_protocol')))
                rec["date_end"] = emdash.config.gettime()
                rec = emdash.config.db().record.put(rec)
            except:
                emdash.log.msg("Error ending session")

        super(MicroscopeUpload, self).end_session()
    
    
    ######################
    # Wizards!!
    ######################
    
    @QtCore.pyqtSlot()
    def _newmicroscopy_wizard(self):
        wizard = emdash.emwizard.NewMicroscopyWizard(parent=self, selected=self.names)
        wizard.signal_done.connect(self.begin_session, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()

    @QtCore.pyqtSlot()
    def _name_microscopy_wizard(self):
        d = QtGui.QInputDialog(self)
        d.setLabelText("Microscopy Record ID")
        d.textValueSelected.connect(self.__select_microscopy, type=QtCore.Qt.QueuedConnection)
        d.exec_()

    @QtCore.pyqtSlot(unicode)
    def __select_microscopy(self, name):
        self.begin_session([], {emdash.config.get('session_protocol'): name})
    
    @QtCore.pyqtSlot()
    def _edit_microscopy_wizard(self):
        # Edit the microscopy session we just created to fill in details
        wizard = emdash.emwizard.EditMicroscopyWizard(parent=self, selected=self.names)
        wizard.signal_done.connect(self.edit_records, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()
    
    #########
    
    @QtCore.pyqtSlot()
    def _newfreezing_wizard(self):
        wizard = emdash.emwizard.NewFreezingWizard(parent=self, selected=self.names)
        wizard.signal_done.connect(self.edit_records, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()

    # These may return a grid_imaging record,
    #     which will cause the target to be updated.
    
    @QtCore.pyqtSlot()
    def _newgrid_wizard(self):
        wizard = emdash.emwizard.NewGridWizard(parent=self, selected=self.names)
        wizard.signal_done.connect(self.edit_records, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()

    @QtCore.pyqtSlot()
    def _newgrid_simple_wizard(self):
        wizard = emdash.emwizard.NewGridSimpleWizard(parent=self, selected=self.names)
        wizard.signal_done.connect(self.edit_records, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()


    @QtCore.pyqtSlot()
    def _edit_grid_wizard(self):
        if self.names.get('grid_imaging') != None:
            wizard = emdash.emwizard.EditGridImagingWizard(parent=self, selected=self.names)
            wizard.signal_done.connect(self.edit_records, type=QtCore.Qt.QueuedConnection)
            wizard.exec_()    
    
    # Manually set target

    @QtCore.pyqtSlot()
    def _select_grid_wizard(self):
        wizard = emdash.emwizard.SelectGridWizard(parent=self, selected=self.names)
        wizard.signal_done.connect(self.set_target, type=QtCore.Qt.QueuedConnection)
        wizard.exec_()

    #################
    # Comments about ice quality
    #################

    @QtCore.pyqtSlot()
    def _assess_ice_thick(self):
        value = unicode(self.ui.assess_ice_thick.currentText())
        # name = self.names.get("_target", -1)
        name = self.target
        if name < 0:
            self.error("Could not set the ice thickness because you have not yet created a grid imaging session")
            return
        self.set(name, "assess_ice_thick", value)
    
    @QtCore.pyqtSlot()        
    def _assess_ice_comments(self):
        value = unicode(self.ui.assess_ice_comments.currentText())
        # name = self.names.get("_target", -1)
        name = self.target
        if name < 0:
            self.error("Could not set the ice conditions because you have not yet created a grid imaging session")
            return
        self.set(name, "assess_ice_comments", value)


def main():
    emdash.upload.main(appclass=MicroscopeUpload)

if __name__ == "__main__":
    main()
    
    