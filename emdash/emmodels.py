import Queue
import collections
import datetime
import operator
import os
import time

from PyQt4 import QtCore, QtGui, Qt

import emdash.config

##############################
# Queue model
##############################

class QueueFile(dict):
    pass

# These two classes adapted from Qt Examples, for obvious reasons..
class DictItem(object):    
    def __init__(self, data, parent=None, cols=None):
        self.parentItem = parent
        self.data = data
        self.childItems = []
        self.cols = cols or []

    def get(self, key, default=None):
        return self.data.get(key, default)

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        try:
            return self.childItems[row]
        except:
            return None

    def childCount(self):
        return len(self.childItems)

    def childNumber(self):
        if self.parentItem != None:
            return self.parentItem.childItems.index(self)
        return 0

    def columnCount(self):
        return len(self.data)

    def data(self, column):
        # cols = ["_recname", "tem_magnification_set", "ctf_defocus_set", 'tem_dose_rate', 'time_exposure_tem', "assess_image_quality", "_status"]
        return self.data.get(self.cols[column])

    def parent(self):
        return self.parentItem        
        
class QueueModel(QtCore.QAbstractItemModel):
    """Display files and status."""    
    itemclass = DictItem
    
    def __init__(self, headers=None, headernames=None, headerwidths=None, parent=None):
        super(QueueModel, self).__init__(parent)
        # Current microscope settings...        
        default_headers = ["_recname", "_status"]
        default_headernames = ["Name", "Status"]
        self.headers = headers or default_headers
        self.headernames = headernames or default_headernames
        self.target = None
        self.rootItem = self.itemclass(QueueFile({}), parent=None, cols=self.headers)
        self.targets = {}
        self.mdata = {}

    @QtCore.pyqtSlot(unicode)
    def set_target(self, target):
        target = unicode(target)
        # Begin a new upload target...
        if self.target == target:
            return
            
        self.target = target
        data = {
            "name":target,
            "_recname":"Record: %s"%target, 
            "_status":"(view)"
        }
        # ian: fix this..
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())            
        treeitem = self.itemclass(data, parent=self.rootItem, cols=self.headers)
        self.rootItem.appendChild(treeitem)
        self.endInsertRows()
        # Save the current name, so new items in the queue will be sent to it
        self.targets[target] = treeitem
        
    @QtCore.pyqtSlot(unicode, object)
    def newfile(self, name, data=None):
        """Add a file to the queue."""
        data = data or {}
        name = unicode(name)
        target = data.get("_target")
        if target is None or not self.targets.get(target):
            raise Exception, "No target!"
        
        if not data.get("_recname"):
            data['_recname'] = name

        ######################################
        # Add the item to the model
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        d = self.itemclass(data, parent=self.targets[target], cols=self.headers)
        self.targets[target].appendChild(d)
        self.endInsertRows()

        ######################################
        # Index by filename        
        self.mdata[name] = d
    
    # Listen for updates
    @QtCore.pyqtSlot(unicode, object)
    def file_status(self, name, data):
        """Update the status dict for a file"""
        self._updatestatus(name, data)

    @QtCore.pyqtSlot(unicode, object)
    def file_success(self, name, data):
        """A file has been successfully uploaded into the db"""
        data['_status'] = "%s"%data.get("name")
        self._updatestatus(name, data)

    @QtCore.pyqtSlot(unicode, str)
    def file_failure(self, name, e):
        """There was an error uploading file"""
        self._updatestatus(name, {"_error": e, "_status": "Retry: %s"%e})

    def _updatestatus(self, name, d):
        # Access by filename
        data = self.mdata.get(unicode(name))
        # ...or access by Record name
        if not data:
            for k,v in self.mdata.items():
                if str(v.get('name')) == name:
                    data = v        
        # If we aren't managing this item, quit    
        if not data:
            return
                
        # Update the row        
        data.data.update(d)
        parentItem = data.parent()
        i = self.createIndex(parentItem.childNumber(), 0, parentItem)
        j = self.createIndex(parentItem.childNumber(), 4, parentItem)
        self.dataChanged.emit(i,j)

    def data(self, index, role):
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole and role != QtCore.Qt.EditRole:
            return None
        item = self.getItem(index)
        col = self.headers[index.column()]        
        return item.data.get(col)

    def getmdata(self, index):
        item = self.getItem(index)
        return item.data

    def flags(self, index):
        if not index.isValid():
            return 0
        return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item
        return self.rootItem

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.headernames[section]
        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return QtCore.QModelIndex()
        parentItem = self.getItem(parent)
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        childItem = self.getItem(index)
        parentItem = childItem.parent()
        if parentItem == self.rootItem:
            return QtCore.QModelIndex()
        return self.createIndex(parentItem.childNumber(), 0, parentItem)

    def rowCount(self, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        return parentItem.childCount()

    def columnCount(self, parent=QtCore.QModelIndex()):
        return len(self.headers)

##############################
# Tree model
##############################

# These two classes adapted from Qt Examples, for obvious reasons..
class TreeItem(object):    
    def __init__(self, data, parent=None):
        self.parentItem = parent
        self.itemData = data
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def childNumber(self):
        if self.parentItem != None:
            return self.parentItem.childItems.index(self)
        return 0

    def columnCount(self):
        return len(self.itemData)

    def data(self, column):
        return self.itemData[column]

    # ian: added this..
    def insertChild(self, position, data):
        if position < 0 or position > len(self.childItems):
            return False
        item = TreeItem(data, self)
        self.childItems.insert(position, item)

    def insertChildren(self, position, count, columns):
        if position < 0 or position > len(self.childItems):
            return False
        for row in range(count):
            data = [None for v in range(columns)]
            item = self.__class__(data=data, parent=self)
            self.childItems.insert(position, item)
        return True

    def insertColumns(self, position, columns):
        if position < 0 or position > len(self.itemData):
            return False
        for column in range(columns):
            self.itemData.insert(position, None)
        for child in self.childItems:
            child.insertColumns(position, columns)
        return True

    def parent(self):
        return self.parentItem

    def removeChildren(self, position, count):
        if position < 0 or position + count > len(self.childItems):
            return False
        for row in range(count):
            self.childItems.pop(position)
        return True

    def removeColumns(self, position, columns):
        if position < 0 or position + columns > len(self.itemData):
            return False
        for column in range(columns):
            self.itemData.pop(position)
        for child in self.childItems:
            child.removeColumns(position, columns)
        return True

    def setData(self, column, value):
        if column < 0 or column >= len(self.itemData):
            return False
        self.itemData[column] = value
        return True

class TreeModel(QtCore.QAbstractItemModel):
    itemclass = TreeItem
    def __init__(self, headers, data, parent=None):
        super(TreeModel, self).__init__(parent)
        rootData = [header for header in headers]
        self.rootItem = self.itemclass(rootData)
        self.setupModelData(data, parent=self.rootItem)        
        #self.setupModelData(data.split("\n"), self.rootItem)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return self.rootItem.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole and role != QtCore.Qt.EditRole:
            return None
        item = self.getItem(index)
        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return 0
        return QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def getItem(self, index):
        if index.isValid():
            item = index.internalPointer()
            if item:
                return item
        return self.rootItem

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.rootItem.data(section)
        return None

    def index(self, row, column, parent=QtCore.QModelIndex()):
        if parent.isValid() and parent.column() != 0:
            return QtCore.QModelIndex()
        parentItem = self.getItem(parent)
        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def insertColumns(self, position, columns, parent=QtCore.QModelIndex()):
        self.beginInsertColumns(parent, position, position + columns - 1)
        success = self.rootItem.insertColumns(position, columns)
        self.endInsertColumns()
        return success

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginInsertRows(parent, position, position + rows - 1)
        success = parentItem.insertChildren(position, rows,
                self.rootItem.columnCount())
        self.endInsertRows()
        return success

    # ian: added this...
    def appendChild(self, data, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginInsertRows(parent, 0, 0)
        success = parentItem.insertChild(0, data)
        self.endInsertRows()
        return success

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
        childItem = self.getItem(index)
        parentItem = childItem.parent()
        if parentItem == self.rootItem:
            return QtCore.QModelIndex()
        return self.createIndex(parentItem.childNumber(), 0, parentItem)

    def removeColumns(self, position, columns, parent=QtCore.QModelIndex()):
        self.beginRemoveColumns(parent, position, position + columns - 1)
        success = self.rootItem.removeColumns(position, columns)
        self.endRemoveColumns()
        if self.rootItem.columnCount() == 0:
            self.removeRows(0, rowCount())
        return success

    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        self.beginRemoveRows(parent, position, position + rows - 1)
        success = parentItem.removeChildren(position, rows)
        self.endRemoveRows()
        return success

    def rowCount(self, parent=QtCore.QModelIndex()):
        parentItem = self.getItem(parent)
        return parentItem.childCount()

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        if role != QtCore.Qt.EditRole:
            return False
        item = self.getItem(index)
        result = item.setData(index.column(), value)
        if result:
            self.dataChanged.emit(index, index)
        return result

    def setHeaderData(self, section, orientation, value, role=QtCore.Qt.EditRole):
        if role != QtCore.Qt.EditRole or orientation != QtCore.Qt.Horizontal:
            return False
        result = self.rootItem.setData(section, value)
        if result:
            self.headerDataChanged.emit(orientation, section, section)
        return result

    def setupModelData(self, data=None, parent=None):
        pass

class RecordTreeModel(TreeModel):
    def __init__(self, root=None, recnames=None, paths=None, parent=None, recurse=1):
        headers = ["Record Name"]
        self.recurse = recurse
        self.recnames = recnames
        self.root = root
        super(RecordTreeModel, self).__init__(data=paths, headers=headers, parent=parent)

    def setupModelData(self, data, parent=None):
        # ian: much simplified!!!!!
        parents = {}
        parents[str(self.root)] = parent
        stack = [str(self.root)]
        seen = set()
        while stack:
            item = stack.pop()
            items = map(str, data.get(item, []))
            # Insert in sorted order
            items = sorted(items, key=lambda x:self.recnames.get(x, '').lower())
            for i in items:
                # print "inserting...", i, self.recnames.get(i), parents[item]
                if i in seen:
                    continue
                seen.add(i)
                treeitem = TreeItem([self.recnames.get(i,i), i], parents[item])
                parents[i] = treeitem
                parents[item].appendChild(treeitem)
                stack.append(i)
                