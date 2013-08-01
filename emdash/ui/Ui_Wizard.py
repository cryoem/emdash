# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Ui_Wizard.ui'
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

class Ui_Wizard(object):
    def setupUi(self, Wizard):
        Wizard.setObjectName(_fromUtf8("Wizard"))
        Wizard.resize(329, 355)
        self.verticalLayout = QtGui.QVBoxLayout(Wizard)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.label_help = QtGui.QLabel(Wizard)
        self.label_help.setText(_fromUtf8(""))
        self.label_help.setTextFormat(QtCore.Qt.RichText)
        self.label_help.setWordWrap(True)
        self.label_help.setOpenExternalLinks(True)
        self.label_help.setObjectName(_fromUtf8("label_help"))
        self.verticalLayout.addWidget(self.label_help)
        self.line = QtGui.QFrame(Wizard)
        self.line.setFrameShape(QtGui.QFrame.HLine)
        self.line.setFrameShadow(QtGui.QFrame.Sunken)
        self.line.setObjectName(_fromUtf8("line"))
        self.verticalLayout.addWidget(self.line)
        self.layout = QtGui.QVBoxLayout()
        self.layout.setObjectName(_fromUtf8("layout"))
        self.verticalLayout.addLayout(self.layout)

        self.retranslateUi(Wizard)
        QtCore.QMetaObject.connectSlotsByName(Wizard)

    def retranslateUi(self, Wizard):
        Wizard.setWindowTitle(QtGui.QApplication.translate("Wizard", "WizardPage", None, QtGui.QApplication.UnicodeUTF8))

