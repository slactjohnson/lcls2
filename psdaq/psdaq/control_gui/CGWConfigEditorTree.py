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

from psdaq.control_gui.QWTree import QWTree, QStandardItemModel, QStandardItem, Qt, QModelIndex, QAbstractItemView
from psdaq.control_gui.QWIcons import icon
from psdaq.control_gui.QWPopupEditText import QWPopupEditText, QDialog
from psdaq.control_gui.QWPopupSelectItem import popup_select_item_from_list
from psdaq.control_gui.CGJsonUtils import json_from_str

from psdaq.configdb.typed_json import updateValue, getType #, getValue
import ast
#import re
#--------------------

def str_is_int(s):
    return s.isdigit() or (s.startswith('-') and s[1:].isdigit())
    #return re.match(r"[-+]?\d+$", s) is not None
    #return re.match(r"^[-+]?[0-9]+$", s) is not None
    #return re.match("^([+-]?[1-9]\d*|0)$", s) is not None

def str_is_hex(s):
    return '0x' in s 
    #return re.fullmatch(r"^[0-9a-fA-F]$", s or "") is not None

def str_is_oct(s):
    return '0o' in s 
    #return re.match(r"\b0o[0-7]+\b", s) is not None

def str_is_bin(s):
    return '0b' in s 

def str_is_any_int(s):
    return str_is_int(s)\
        or str_is_hex(s)\
        or str_is_oct(s)\
        or str_is_bin(s)

def path_to_item(item):
    #if item is None : return None
    parent = item.parent()
    s = item.text().split(' ')[0]
    return s if parent is None else '%s.%s'%(path_to_item(parent), s)

#--------------------

class CGWConfigEditorTree(QWTree) :
    """Tree-like configuration editor widget
    """
    def __init__(self, **kwargs) :

        parent = kwargs.get('parent',None)
        self.dictj        = kwargs.get('dictj', {'i_test':12345,'o_test':0o377,'h_test':0xffea,'b_test':12345})
        self.list_max_len = kwargs.get('list_max_len',5)

        QWTree.__init__(self, parent)
        self.setWordWrap(True)

        icon.set_icons()
        #self.clicked[QModelIndex].connect(self.on_click)
        #self.doubleClicked[QModelIndex].connect(self.on_double_click)
        self.model.itemChanged.connect(self.on_item_changed)
        #self.connect_item_selected_to(self.on_item_selected)
        self.disconnect_item_selected_from(self.on_item_selected)
        #self.clicked[QModelIndex].disconnect(self.on_click)

#--------------------

    def set_tool_tips(self) :
        QWTree.set_tool_tips(self)
        self.setToolTip('Tree-like configuration editor')

#--------------------

    def fill_tree_model(self):
        """Re-implementation of the superclass method
        """
        self.fill_tree_model_from_dict()

#--------------------

    def fill_tree_model_from_dict(self):
        self.clear_model()
        dj = self.dictj
        if not isinstance(dj, dict) :
            logger.warning('Loaded configuration object is not a dict....')
            return
        self.tree_model_from_dict(dj, self.model.invisibleRootItem())

#--------------------

    def str_object_type(self, o) :
        return 'str'    if isinstance(o, str) else\
               'int'    if isinstance(o, int) else\
               'float'  if isinstance(o, float) else\
              ('list [%s, %d]' % (self.str_object_type(o[0]), len(o))) if isinstance(o, list) else\
               str(type(o))

#--------------------

    def data_type(self, item, o):
        if item is None : return None
        path = path_to_item(item)
        if path is None : return None

        dtype = None
        try    : dtype = getType(self.dictj, path)
        except : pass; # logger.warning("getType can't retreive dtype for path: %s" % path)

        dtype = str(dtype)
        return dtype

#--------------------

    def enum_dicts(self, dtype) :
        d = json_from_str(dtype) if (isinstance(dtype,str) and len(dtype) and(dtype[0] == '{')) else None
        if isinstance(d, dict) : return True, d, {v:k for k,v in d.items()}
        return False, None, None

#--------------------

    def tree_model_from_dict(self, o, parent_item, is_read_only=False):
        """Recursive (json) dictionary conversion to the model tree.
           presentation convention:
           - setText           - text displaied in the tree model
           - setAccessibleText - bare text from fields in dictj
           - setAccessibleDescription - preserves internal data types: dict, list, data
        """

        #self.setEditTriggers(QAbstractItemView.DoubleClicked) #AnyKeyPressed) # SelectedClicked
        #self.setEditTriggers(QAbstractItemView.SelectedClicked)

        if isinstance(o, dict) :
            parent_item.setAccessibleText(parent_item.text())
            parent_item.setText('%s *' % parent_item.text())
            parent_item.setAccessibleDescription('key-to-dict')
            parent_item.setToolTip('key to dict object')
            for k,v in o.items() :
                if k==':types:' : continue
                is_RO = is_read_only or (':RO' in k)

                # completely HIDE :RO
                if is_RO and not k=='help:RO': continue

                item = QStandardItem(k)
                item.setIcon(icon.icon_folder_closed)
                item.setEditable(False)
                #item.setToolTip('...') # will be filled oot by child item
                #item.setCheckable(True) 
                parent_item.appendRow(item)
                self.tree_model_from_dict(v, item, is_read_only=is_RO)
        elif isinstance(o, list) :
            if any([isinstance(v, (dict,list)) for v in o]) :
                parent_item.setAccessibleDescription('key-to-list-compaund')
                parent_item.setAccessibleText(parent_item.text())
                parent_item.setText('%s *' % parent_item.text())
                parent_item.setToolTip('key to the list of compaund types\n(lists, dicts etc.)')
                for i,v in enumerate(o) :
                    item = QStandardItem('%d'%i)
                    #item.setAccessibleText('%d'%i)
                    item.setEditable(False)
                    item.setIcon(icon.icon_folder_closed)
                    #item.setCheckable(True) 
                    parent_item.appendRow(item)
                    self.tree_model_from_dict(v, item, is_read_only)
            else : # data list
                parent_item.setAccessibleText(parent_item.text())
                parent_item.setText('%s *' % parent_item.text())
                is_trimmed = len(o)>=self.list_max_len
                cmt = 'trimmed list' if is_trimmed else 'list'
                parent_item.setAccessibleDescription('key to the %s' % cmt)
                parent_item.setToolTip('key to the %s' % cmt)
                path = path_to_item(parent_item)
                item = QStandardItem()

                self.set_item_for_list(item, o)

                item.setAccessibleDescription(cmt)
                dtype = self.data_type(parent_item, o)
                item.setToolTip('%s path: [%s] dtype: %s'% (cmt,path,str(dtype)))
                #item.setIcon(icon.icon_table)
                item.setCheckable(False)
                item.setEditable(not (is_trimmed or is_read_only)) 
                item.setEnabled(not is_read_only) 
                parent_item.appendRow(item)
                #print('item: %s data_type: %s' % (item.text(), str(dtype)))
                
        else : # simple data type
                parent_item.setText('%s' % parent_item.text())
                parent_item.setAccessibleDescription('key to data')
                parent_item.setToolTip('key to simple data type')
                path = path_to_item(parent_item)
                dtype = self.data_type(parent_item, o).replace(' ', '').replace("'", '"')

                is_enum, dic_enum, dic_inv = self.enum_dicts(dtype)
                #if is_enum : print('ZZZZZ this is it: %s enum dicts: %s %s' % (str(dtype), str(dic_enum), str(dic_inv)))

                if is_enum:
                    s = dic_inv[o] if o in dic_inv.keys() else next(iter(dic_inv.values()))
                else:
                    s = str(o)
                item = QStandardItem(s)
                item.setAccessibleText(s)
                #item.setAccessibleDescription('data')
                item.setAccessibleDescription(dtype)
                
                item.setToolTip('data path: [%s] dtype: %s'%(path, str(dtype)))
                #item.setToolTip('data path [%s]'%(path))
                #item.setIcon(icon.icon_table)
                item.setEditable(not is_read_only) 
                item.setEnabled(not is_read_only) 
                item.setSelectable(False) 
                item.setCheckable(str_is_any_int(s)) 
                parent_item.appendRow(item)
                #print('XXXX item: %s data_type: %s' % (item.text(), str(dtype)))

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

            descr = item.accessibleDescription()
            is_enum, dic_enum, dic_inv = self.enum_dicts(descr)
            is_trim = descr[:4] == 'trim'
            val_item = item.accessibleText() if is_trim else\
                       dic_enum[item.text()] if is_enum else\
                       item.text()

            #val_type = getType(self.dictj, path)
            #val_dict = getValue(self.dictj, path)
            #print('%s  ==== path: %s  type: %s  dict value: %s  item value: %s'%\
            #      (gap, path, str(val_type), str(val_dict), str(val_item)))

            if updateValue is not None :
               status = updateValue(self.dictj, path, str(val_item))
               if status :
                   logger.warning('CGWConfigEditorTree.updateValue path:[%s] new value: %s bad status: %d' % (path, str(val_item), status))

            else :
               logger.warning("CGWConfigEditorTree.updateValue is None, dictj can't be updated")

#--------------------

    def on_item_changed(self, item):

        if item.hasChildren() : return

        s = item.text()
        #state = ['UNCHECKED', 'TRISTATE', 'CHECKED'][item.checkState()]
        #msg = 'on_item_changed: item "%s", is at state %s' % (s, state)

        #print('on_item_changed item.checkState: %d' % item.checkState())
        if item.checkState() != 2 : return # in case if state is changed not clicking on check box

        #item.setEnabled(False) <<<=== does not work
        self.model.itemChanged.disconnect(self.on_item_changed)

        item.setCheckState(0 if str_is_bin(s) else 1)
        s1 = s
        if   str_is_int(s) : s1 = hex(int(s,10))
        elif str_is_hex(s) : s1 = oct(int(s,16))
        elif str_is_oct(s) : s1 = bin(int(s,8))
        elif str_is_bin(s) : s1 = str(int(s,2))

        msg = 'on_item_changed: item value %s converted to %s' % (s, s1)
        logger.debug(msg)

        item.setText(s1)
        self.model.itemChanged.connect(self.on_item_changed)
        
#--------------------

    def on_click(self, index):
        item = self.model.itemFromIndex(index)
        parent = item.parent()
        spar = parent.text() if parent is not None else None
        #msg = 'xxxxx clicked item: %s parent: %s' % (item.text(), spar) # index.row()
        s = item.text()
        msg = ''
        if str_is_int(s) :
            d = ast.literal_eval(s)
            b,o,h = bin(d), oct(d), hex(d)
            msg = 'clicked item dec: %s hex: %s oct: %s bin: %s' % (s,h,o,b)
            logger.debug(msg)
        #else : 
        #    logger.debug('clicked item: %s is not a digit' % s)

        if self.start_special_editor(index) : return
        self.edit(index)

#--------------------

    def on_double_click(self, index):
        pass
        #self.start_special_editor(index)

#--------------------

    def start_special_editor(self, index):
        """start editor for
           - enumerated values
           - long "trimmed" arrays
        """
        item = self.model.itemFromIndex(index)
        #msg = 'on_double_click item in row:%02d text: %s acc-text: %s' % (index.row(), item.text(), item.accessibleText())
        #logger.debug(msg)

        item_parent = item.parent()
        if item_parent is not None :
            path = path_to_item(item.parent())
            #print('XXX path_to_item: %s' % path)

        txt = item.accessibleText()
        descr = item.accessibleDescription()
        is_enum, dic_enum, dic_inv = self.enum_dicts(descr)

        # start editor for enumerated values
        if is_enum :
            #print('XXX TBD enum editor for txt: %s and dict: %s' % (txt, str(dic_enum)))
            selected = popup_select_item_from_list(self, dic_enum.keys(), dx=-20, dy=-10, use_cursor_pos=True, do_sort=False)
            if selected is None : return True
            self.set_item_for_list(item, selected)
            return True

        # start editor for long "trimmed" arrays
        #print('descr: "%s"' % descr[:7])
        if descr[:7] == 'trimmed' : 
            #logger.info('select_ifname %s' % self.ifname)
            w = QWPopupEditText(parent=self, text=txt)
            #w.move(self.pos() + QPoint(self.width()+5, 0))
            resp=w.exec_()
            logger.debug('resp: %s' % {QDialog.Rejected:'Rejected', QDialog.Accepted:'Accepted'}[resp])
            if resp == QDialog.Rejected : return True

            txt_new = w.get_content()
            self.set_item_for_list(item, txt_new)
            #print('TBD on_double_click edited: %s' % txt_new)
            return True

        return False

#--------------------

    def closeEvent(self, e):
        logger.debug('CGWConfigEditorTree.closeEvent')
        QWTree.closeEvent(self, e)

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
