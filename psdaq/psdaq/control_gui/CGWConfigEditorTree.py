#--------------------
"""
:py:class:`CGWConfigEditorTree` - widget for configuration editor
============================================================================================

Usage::

    # Import
    from psdaq.control_gui.CGWConfigEditorTree import CGWConfigEditorTree

    # Methods - see test

See:
    - :py:class:`CGWConfigEditorTree`
    - `lcls2 on github <https://github.com/slac-lcls/lcls2/psdaq/psdaq/control_gui>`_.

This software was developed for the LCLS2 project.
If you use all or part of it, please give an appropriate acknowledgment.

Created on 2019-03-14 by Mikhail Dubrovin
"""
#--------------------

import logging
logger = logging.getLogger(__name__)

#from psana.graphqt.QWTree import QWTree, QStandardItemModel, QStandardItem, Qt, QModelIndex
from psdaq.control_gui.QWTree import QWTree, QStandardItemModel, QStandardItem, Qt, QModelIndex
from psdaq.control_gui.QWIcons import icon
from psdaq.control_gui.QWPopupEditText import QWPopupEditText, QDialog


updateValue = None
#from psana.dgramPort.typed_json import updateValue # getType, getValue, 
try    : from psana.dgramPort.typed_json import updateValue # getType, getValue, 
except : 
    msg = "!!!!! WARNING: can't import updateValue because of problem with psana.psana.__init__.py"
    print(msg)
    logger.warning(msg)

#from psana.dgramPort.typed_json import getType

#--------------------

def path_to_item(item):
    #if item is None : return None
    parent = item.parent()
    s = item.text().split(' - ')[0]
    return s if parent is None else '%s.%s'%(path_to_item(parent), s)

#--------------------

class CGWConfigEditorTree(QWTree) :
    """Tree-like configuration editor widget
    """
    def __init__(self, **kwargs) :

        parent = kwargs.get('parent',None)
        self.dictj        = kwargs.get('dictj', {'a_test':0,'b_test':1})
        self.parent_ctrl  = kwargs.get('parent_ctrl',None)
        self.list_max_len = kwargs.get('list_max_len',5)

        QWTree.__init__(self, parent)

        icon.set_icons()
        self.doubleClicked[QModelIndex].connect(self.on_double_click)

#--------------------

    def set_tool_tips(self) :
        QWTree.set_tool_tips(self)
        self.setToolTip('Tree-like configuration editor')

#--------------------

#    def set_style(self) :
#        QWTree.set_style(self)
 
#--------------------

    def fill_tree_model(self):
        """Re-implementation of the superclass method
        """
        self.fill_tree_model_from_dict()
        #self.fill_tree_model_test()

#--------------------

    def fill_tree_model_from_dict(self):
        self.clear_model()
        dj = self.dictj
        if not isinstance(dj, dict) :
            logger.warning('Loaded configuration object is not a dict....')
            return
        self.tree_model_from_dict(dj, self.model.invisibleRootItem())

#--------------------

    def data_type(self, item):
        if item is None : return None
        path = path_to_item(item)
        if path is None : return None
        #dtype = getType(self.dictj, path)
        #print('XXXXXX path: %s dtype: %s' % (path, str(dtype)))
        return 'dtype is N/A'

#--------------------

    def data_type_v0(self, item):
        if item is None : return None
        path = path_to_item(item)
        #print('XXXXXXXX path:%s'%path)
        if path is None : return None
        v=self.dictj[':types:']
        #print('       :types:%s'%str(v))
        for k in path.split('.') :
            #print('===k: %s type: %s value: %s' % (k, type(v), str(v)))
            #if k==':enum:' : continue
            ind = int(k) if k.isdigit() else k # ducking for list indeces
            v = v[ind] if v is not None else None
        return v

#--------------------

    def tree_model_from_dict(self, o, parent_item):
        """Recursive (json) dictionary conversion to the model tree.
           - setText - show keywords from dict to display in the tree model
           - setAccessibleText - processing specific comments
           - setAccessibleDescription - preserves internal data types: dict, list, data

        """
        if isinstance(o, dict) :
            parent_item.setAccessibleText(parent_item.text())
            parent_item.setText('%s - key to dict' % parent_item.text())
            parent_item.setAccessibleDescription('key-to-dict')
            parent_item.setToolTip('key to dict object')
            for k,v in o.items() :
                if k==':types:' : return
                item = QStandardItem(k)
                item.setIcon(icon.icon_folder_closed)
                item.setEditable(False)
                #item.setToolTip('...') # will be filled oot by child item
                #item.setCheckable(True) 
                parent_item.appendRow(item)
                self.tree_model_from_dict(v, item)
        elif isinstance(o, list) :
            if any([isinstance(v, (dict,list)) for v in o]) :
                parent_item.setAccessibleDescription('key-to-list-compaund')
                parent_item.setAccessibleText(parent_item.text())
                parent_item.setText('%s - key to list of compaund' % parent_item.text())
                parent_item.setToolTip('key to the list of compaund types\n(lists, dicts etc.)')
                for i,v in enumerate(o) :
                    item = QStandardItem('%d'%i)
                    #item.setAccessibleText('%d'%i)
                    item.setEditable(False)
                    item.setIcon(icon.icon_folder_closed)
                    #item.setCheckable(True) 
                    parent_item.appendRow(item)
                    self.tree_model_from_dict(v, item)
            else : # data list
                parent_item.setAccessibleText(parent_item.text())
                parent_item.setText('%s - key to list' % parent_item.text())
                is_trimmed = len(o)>=self.list_max_len
                cmt = 'trimmed list' if is_trimmed else 'list'
                parent_item.setAccessibleDescription('key to the %s' % cmt)
                parent_item.setToolTip('key to the %s' % cmt)
                path = path_to_item(parent_item)
                item = QStandardItem()

                self.set_item_for_list(item, o)

                item.setAccessibleDescription(cmt)
                dtype = self.data_type(parent_item)
                item.setToolTip('%s path: [%s] dtype: %s'% (cmt,path,str(dtype)))
                #item.setIcon(icon.icon_table)
                item.setCheckable(True) 
                item.setEditable(not is_trimmed) 
                parent_item.appendRow(item)
                #print('item: %s data_type: %s' % (item.text(), str(dtype)))
                
        else : # simple data type
                parent_item.setText('%s' % parent_item.text())
                parent_item.setAccessibleDescription('key to data')
                parent_item.setToolTip('key to simple data type')
                path = path_to_item(parent_item)
                item = QStandardItem('%s' % str(o))
                item.setAccessibleText(str(o))
                item.setAccessibleDescription('data')
                dtype = self.data_type(parent_item)
                item.setToolTip('data path: [%s] dtype: %s'%(path, str(dtype)))
                #item.setToolTip('data path [%s]'%(path))
                #item.setIcon(icon.icon_table)
                item.setCheckable(True) 
                parent_item.appendRow(item)
                #print('item: %s data_type: %s' % (item.text(), str(dtype)))

#--------------------

    def set_item_for_list(self, item, o):
        """set final data item using list or str object
        """
        # convert input object to the list of str values
        lst = o.replace('\n',' ').split(' ') if isinstance(o, str) else\
              [str(v) for v in o]            if isinstance(o, list) else\
              ['N/A',]
        is_trimmed = len(lst)>=self.list_max_len
        text_tot = str(' '.join(lst))
        text = ('%s ...' % (' '.join(lst[:self.list_max_len]))) if is_trimmed else text_tot
        item.setText(text)
        item.setAccessibleText(text_tot)

#--------------------

    def update_dict_for_tree_model(self, dj, parent_item):
        """Recursive conversion of the tree model to (json) dictionary.
        """
        logger.debug('CGWConfigEditorTree.update_dict_from_tree_model - TBE')
        path

#--------------------

    def fill_tree_model_test(self):
        self.clear_model()
        for k in range(0, 4):
            parentItem = self.model.invisibleRootItem()
            parentItem.setIcon(icon.icon_folder_open)
            for i in range(0, k):
                item = QStandardItem('itemA %s %s'%(k,i))
                item.setIcon(icon.icon_table)
                item.setCheckable(True) 
                parentItem.appendRow(item)

                item = QStandardItem('itemB %s %s'%(k,i))
                item.setIcon(icon.icon_folder_closed)
                parentItem.appendRow(item)
                parentItem = item
                logger.debug('append item %s' % (item.text()))

#--------------------

    def set_content(self, dictj) :  
        """Interface method
        """
        self.dictj = dictj
        self.fill_tree_model_from_dict()

#--------------------
 
    def get_content(self):
        """Interface method
        """
        logger.debug('CGWConfigEditorTree.get_content')
        top_item=self.model.invisibleRootItem()
        self.iterate_over_children(top_item)
        #sj = str_json(dictj)
        #dj = json_from_str()
        return self.dictj

#--------------------
 
    def iterate_over_children(self, item, gap='  '):
        """
        """
        #print('%s%s ==== %s ==== %s' % (gap, item.text(), item.accessibleText(), item.accessibleDescription()))

        if item.hasChildren() : 
            for r in range(item.rowCount()):
                self.iterate_over_children(item.child(r,0), gap=gap+'  ')

        else : # process data field
            path = path_to_item(item.parent())
            val_item = item.accessibleText()
            #val_type = getType(self.dictj, path)
            #val_dict = getValue(self.dictj, path)
            #print('%s  ==== path: %s  type: %s  dict value: %s  item value: %s'%\
            #      (gap, path, str(val_type), str(val_dict), str(val_item)))

            if updateValue is not None :
               updateValue(self.dictj, path, str(val_item))

#--------------------

    def on_double_click(self, index):
        item = self.model.itemFromIndex(index)
        #msg = 'on_double_click item in row:%02d text: %s acc-text: %s' % (index.row(), item.text(), item.accessibleText())
        #logger.debug(msg)

        item_parent = item.parent()
        if item_parent is not None :
            path = path_to_item(item.parent())
            #print('XXX path_to_item: %s' % path)

        descr = item.accessibleDescription()
        #print('descr: "%s"' % descr[:7])
        if descr[:7] != 'trimmed' : return

        txt = item.accessibleText()

        #logger.info('select_ifname %s' % self.ifname)
        w = QWPopupEditText(parent=self, text=txt)
        #w.move(self.pos() + QPoint(self.width()+5, 0))
        resp=w.exec_()
        logger.debug('resp: %s' % {QDialog.Rejected:'Rejected', QDialog.Accepted:'Accepted'}[resp])
        if resp == QDialog.Rejected : return

        txt_new = w.get_content()
        self.set_item_for_list(item, txt_new)
        #print('TBD on_double_click edited: %s' % txt_new)

#--------------------

#    def closeEvent(self, e):
#        logger.debug('closeEvent')
#        #self.parent_ctrl.w_display = None

#--------------------

    if __name__ == "__main__" :

      def key_usage(self) :
        return 'Keys:'\
               '\n  ESC - exit'\
               '\n  E - expand'\
               '\n  C - collapse'\
               '\n'

      def keyPressEvent(self, e) :
        #logger.debug('keyPressEvent, key = %s'%e.key())       
        if   e.key() == Qt.Key_Escape :
            self.close()

        elif e.key() == Qt.Key_E : 
            self.process_expand()

        elif e.key() == Qt.Key_C : 
            self.process_collapse()

        else :
            logger.debug(self.key_usage())

#--------------------

if __name__ == "__main__" :

    logging.basicConfig(format='%(message)s', level=logging.DEBUG)

    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = CGWConfigEditorTree(parent=None)
    w.setGeometry(10, 25, 400, 800)
    w.show()
    app.exec_()

#--------------------