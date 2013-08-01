import collections
import datetime
import operator
import os
import time
import subprocess

from PyQt4 import QtCore, QtGui, Qt

import emdash.config
import emdash.log

# This has to be in emdash/ui because it is imported
# by the UI files created using UIC.

def starstring(stars):
    return emdash.config.get('starclosed') * stars + emdash.config.get('staropen') * (5-stars)

class ControlMenu(QtGui.QMenu):
    signal_enqueue = QtCore.pyqtSignal(unicode, object)
    signal_dequeue = QtCore.pyqtSignal(unicode, object)
    
    def __init__(self, parent=None, name=None, data=None):
        QtGui.QMenu.__init__(self, parent=parent)
        # ian: is there a better way than passing this dict around..
        self.data = data
        self.name = name
        self.addAction(QtGui.QAction("Add to Queue", self, triggered=self.enqueue))

    def enqueue(self):
        self.signal_enqueue.emit(self.name, self.data)
        
    def dequeue(self):
        self.signal_dequeue.emit(self.name, self.data)

class ProgressBarDelegate(QtGui.QItemDelegate):
    def sizeHint(self, option, index):
        return Qt.QSize(130, 30)
    
    def paint(self, painter, option, index):
        progress = index.model().data(index, QtCore.Qt.DisplayRole)
        
        if isinstance(progress, basestring) or progress == None:
            return QtGui.QItemDelegate.paint(self, painter, option, index)
                
        opts = QtGui.QStyleOptionProgressBarV2()
        opts.rect = option.rect
        opts.minimum = 1
        opts.maximum = 100
        opts.progress = int(progress*100)
        return QtGui.QApplication.style().drawControl(QtGui.QStyle.CE_ProgressBar, opts, painter)

class Delegate(QtGui.QStyledItemDelegate):
    def _gettext(self, data):
        return data

    def paint(self, painter, option, index):
        painter.save()
        # self.drawBackground(painter, option, index)
        rect = option.rect
        rect = QtCore.QRect(rect.left()+3, rect.top()+6, rect.width()-5, rect.height())        
        data = index.model().data(index, QtCore.Qt.DisplayRole)
        if data == None:
            t = ""
        elif data == -1:
            t = "Saving.."
        else:
            t = self._gettext(data)
        QtGui.QApplication.style().drawItemText(painter, rect, 0, option.palette, True, QtCore.QString(t))
        painter.restore()

class StarDelegate(Delegate):
    def _gettext(self, data):
        starmap = {
            0: "Trash",
            1: starstring(1),
            2: starstring(1),
            3: starstring(2),
            4: starstring(2),
            5: starstring(3),
            6: starstring(3),
            7: starstring(4),
            8: starstring(4),
            9: starstring(5),
            10: starstring(5)
        }
        return starmap.get(data)

class Menu(QtGui.QMenu):
    signal_set = QtCore.pyqtSignal(unicode, unicode, unicode)

    def __init__(self, parent=None, name=None, param=None, value=None, choices=None):
        QtGui.QMenu.__init__(self, parent=parent)
        self.choices = choices
        self.value = value
        self.param = param
        self.name = name
        self.init()

    def set(self, value):
        self.signal_set.emit(self.name, self.param, str(value))

    def init(self):
        for value in self.choices:
            lx = lambda value:self.signal_set.emit(self.name, self.param, str(value))
            self.addAction(QtGui.QAction(str(value), self, triggered=lx))

class QualityMenu(Menu):
    def init(self):
        so = emdash.config.get('staropen')
        sc = emdash.config.get('starclosed')
        self.addAction(QtGui.QAction("Trash", self, triggered=self.set_0))
        self.addAction(QtGui.QAction(sc*1+so*4, self, triggered=self.set_1))
        self.addAction(QtGui.QAction(sc*2+so*3, self, triggered=self.set_2))
        self.addAction(QtGui.QAction(sc*3+so*2, self, triggered=self.set_3))
        self.addAction(QtGui.QAction(sc*4+so*1, self, triggered=self.set_4))
        self.addAction(QtGui.QAction(sc*5+so*0, self, triggered=self.set_5))

    def set_0(self):    
        self.set(0)

    def set_1(self):
        self.set(1)

    def set_2(self):    
        self.set(3)

    def set_3(self):    
        self.set(5)

    def set_4(self):    
        self.set(7)

    def set_5(self):    
        self.set(9)

# This is in this directory instead of models so it can be easily imported into the Ui elements

class FilesView(QtGui.QTreeView):    
    signal_dequeue = QtCore.pyqtSignal(unicode, object)
    signal_enqueue = QtCore.pyqtSignal(unicode, object)
    signal_set = QtCore.pyqtSignal(unicode, unicode, unicode)

    def star_column(self, col):
        self.setItemDelegateForColumn(col, StarDelegate(parent=self))
        
    def prog_column(self, col):
        self.setItemDelegateForColumn(col, ProgressBarDelegate(parent=self))
        
    @QtCore.pyqtSlot(unicode, object)
    def newfile(self, filename, data=None):
        """When a new file is discovered, scroll to bottom and expand all"""
        self.expandAll()
        sb = self.verticalScrollBar()
        size = sb.maximum()
        sb.setValue(size)

    def load_viewer(self, filename):
        filename = unicode(filename)
        emdash.log.msg("loading viewer:", filename)
        dname = os.path.dirname(filename)
        subprocess.Popen(['python', '-m', 'e2display', filename], cwd=dname)

    def mousePressEvent(self, event):
        index = self.indexAt(event.pos())
        if index.row() < 0:
            return super(FilesView, self).mousePressEvent(event)    
    
        data = self.model().getmdata(index)
        name = data.get('name', -1)
        headers = self.model().headers
        param = headers[index.column()]    

        ###################
        # View columns    
        if param == "_status":    
            # Launch web browser...
            if data.get("name") != None:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl("%s/record/%s/?ctxid=%s"%(emdash.config.get('host'), data.get("name"), emdash.config.get('ctxid'))))

            else:
                editor = ControlMenu(parent=self, name=data.get("_name"), data=data)
                editor.signal_enqueue.connect(self.signal_enqueue)
                editor.popup(self.mapToGlobal(event.pos()))
        
        elif param == '_recname':
            # Or file viewer
            self.load_viewer(data.get('_filename'))
                                
        ###################
        # Editable columns    
        
        if data.get('name') == None:
            param = None
            
        if param == 'tem_magnification_set':
            d, ok = QtGui.QInputDialog.getDouble(self, "Set Magnification", "Magnification (x1000):", data.get('tem_magnification_set', 0), 0, 1000, 2)
            if ok:
                self.signal_set.emit(name, 'tem_magnification_set', str(d))                

        elif param == 'ctf_defocus_set':
            d, ok = QtGui.QInputDialog.getDouble(self, "Set Defocus", "Defocus (underfocus is positive)", data.get('ctf_defocus_set', 0), -100, 100, 2)
            if ok:
                self.signal_set.emit(name, 'ctf_defocus_set', str(d))                    

        elif param == 'tem_dose_rate':
            d, ok = QtGui.QInputDialog.getDouble(self, "Set Dose Rate", "Dose Rate (e/A2/sec)", data.get('tem_dose_rate', 0), 0, 100, 2)
            if ok:
                self.signal_set.emit(name, 'tem_dose_rate', str(d))                    

        elif param == 'time_exposure_tem':
            d, ok = QtGui.QInputDialog.getDouble(self, "Set Exposure Time", "Exposure Time (s)", data.get('time_exposure_tem', 0), 0, 10, 2)
            if ok:
                self.signal_set.emit(name, 'time_exposure_tem', str(d))                    

        elif param == 'assess_image_quality':
            editor = QualityMenu(parent=self, name=data.get('name'), param='assess_image_quality')
            editor.signal_set.connect(self.signal_set)
            editor.popup(self.mapToGlobal(event.pos()))
            
        return super(FilesView, self).mousePressEvent(event)        
