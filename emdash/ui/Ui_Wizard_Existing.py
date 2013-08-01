# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Ui_Wizard_Existing.ui'
#
# Created: Tue Jul 31 04:19:55 2012
#      by: PyQt4 UI code generator 4.9.1
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

class Ui_Wizard_Existing(object):
    def setupUi(self, Wizard_Existing):
        Wizard_Existing.setObjectName(_fromUtf8("Wizard_Existing"))
        Wizard_Existing.resize(329, 355)
        self.verticalLayout = QtGui.QVBoxLayout(Wizard_Existing)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.label_help = QtGui.QLabel(Wizard_Existing)
        self.label_help.setText(_fromUtf8(""))
        self.label_help.setTextFormat(QtCore.Qt.RichText)
        self.label_help.setWordWrap(True)
        self.label_help.setOpenExternalLinks(True)
        self.label_help.setObjectName(_fromUtf8("label_help"))
        self.verticalLayout.addWidget(self.label_help)
        self.line = QtGui.QFrame(Wizard_Existing)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName(_fromUtf8("line"))
        self.verticalLayout.addWidget(self.line)
        self.layout = QtGui.QVBoxLayout()
        self.layout.setObjectName(_fromUtf8("layout"))
        self.radio_existing = QtGui.QRadioButton(Wizard_Existing)
        self.radio_existing.setChecked(False)
        self.radio_existing.setObjectName(_fromUtf8("radio_existing"))
        self.layout.addWidget(self.radio_existing)
        self.tree_records = QtGui.QTreeView(Wizard_Existing)
        self.tree_records.setObjectName(_fromUtf8("tree_records"))
        self.layout.addWidget(self.tree_records)
        self.verticalLayout.addLayout(self.layout)

        self.retranslateUi(Wizard_Existing)
        QtCore.QMetaObject.connectSlotsByName(Wizard_Existing)

    def retranslateUi(self, Wizard_Existing):
        Wizard_Existing.setWindowTitle(QtGui.QApplication.translate("Wizard_Existing", "WizardPage", None, QtGui.QApplication.UnicodeUTF8))
        self.radio_existing.setText(QtGui.QApplication.translate("Wizard_Existing", "Select from list", None, QtGui.QApplication.UnicodeUTF8))

