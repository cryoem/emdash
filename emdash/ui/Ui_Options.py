# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'Ui_Options.ui'
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

class Ui_Options(object):
    def setupUi(self, Options):
        Options.setObjectName(_fromUtf8("Options"))
        Options.resize(500, 600)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(Options.sizePolicy().hasHeightForWidth())
        Options.setSizePolicy(sizePolicy)
        self.verticalLayout = QtGui.QVBoxLayout(Options)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.layout_options = QtGui.QFormLayout()
        self.layout_options.setSizeConstraint(QtGui.QLayout.SetMinimumSize)
        self.layout_options.setFieldGrowthPolicy(QtGui.QFormLayout.ExpandingFieldsGrow)
        self.layout_options.setObjectName(_fromUtf8("layout_options"))
        self.verticalLayout.addLayout(self.layout_options)
        self.buttonBox = QtGui.QDialogButtonBox(Options)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.buttonBox.sizePolicy().hasHeightForWidth())
        self.buttonBox.setSizePolicy(sizePolicy)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(Options)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("accepted()")), Options.accept)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("rejected()")), Options.reject)
        QtCore.QMetaObject.connectSlotsByName(Options)

    def retranslateUi(self, Options):
        Options.setWindowTitle(QtGui.QApplication.translate("Options", "EMDash Options", None, QtGui.QApplication.UnicodeUTF8))

