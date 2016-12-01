#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import pickle
import os
import struct
import portalocker
import os

class ValueRef(object):
    " a reference to a string value on disk"
    def __init__(self, referent=None, address=0):
        self._referent = referent #value to store
        self._address = address #address to store at

    @property
    def address(self):
        return self._address

    def prepare_to_store(self, storage):
        pass

    @staticmethod
    def referent_to_bytes(referent):
        return referent.encode('utf-8')

    @staticmethod
    def bytes_to_referent(bytes):
        return bytes.decode('utf-8')

    def get(self, storage):
        "read bytes for value from disk"
        if self._referent is None and self._address:
            self._referent = self.bytes_to_referent(storage.read(self._address))
        return self._referent

    def store(self, storage):
        "store bytes for value to disk"
        #called by BinaryNode.store_refs
        if self._referent is not None and not self._address:
            self.prepare_to_store(storage)
            self._address = storage.write(self.referent_to_bytes(self._referent))

class BinaryNodeRef(ValueRef):
    "reference to a btree node on disk"

    #calls the BinaryNode's store_refs
    def prepare_to_store(self, storage):
        "have a node store its refs"
        if self._referent:
            self._referent.store_refs(storage)

    @staticmethod
    def referent_to_bytes(referent):
        "use pickle to convert node to bytes"
        return pickle.dumps({
            'left': referent.left_ref.address,
            'key': referent.key,
            'value': referent.value_ref.address,
            'right': referent.right_ref.address,
        })

    @staticmethod
    def bytes_to_referent(string):
        "unpickle bytes to get a node object"
        d = pickle.loads(string)
        return BinaryNode(
            BinaryNodeRef(address=d['left']),
            d['key'],
            ValueRef(address=d['value']),
            BinaryNodeRef(address=d['right']),
        )

class BinaryNode(object):
    @classmethod
    def from_node(cls, node, **kwargs):
        "clone a node with some changes from another one"
        return cls(
            left_ref=kwargs.get('left_ref', node.left_ref),
            key=kwargs.get('key', node.key),
            value_ref=kwargs.get('value_ref', node.value_ref),
            right_ref=kwargs.get('right_ref', node.right_ref),
        )

    def __init__(self, left_ref, key, value_ref, right_ref):
        self.left_ref = left_ref
        self.key = key
        self.value_ref = value_ref
        self.right_ref = right_ref

    def store_refs(self, storage):
        "method for a node to store all of its stuff"
        self.value_ref.store(storage)
        #calls BinaryNodeRef.store. which calls
        #BinaryNodeRef.prepate_to_store
        #which calls this again and recursively stores
        #the whole tree
        self.left_ref.store(storage)
        self.right_ref.store(storage)

class BinaryTree(object):
    "Immutable Binary Tree class. Constructs new tree on changes"
    def __init__(self, storage):
        self._storage = storage
        self._refresh_tree_ref()

    def commit(self):
        "changes are final only when committed"
        #triggers BinaryNodeRef.store
        self._tree_ref.store(self._storage)
        #make sure address of new tree is stored
        self._storage.commit_root_address(self._tree_ref.address)

    def _refresh_tree_ref(self):
        "get reference to new tree if it has changed"
        self._tree_ref = BinaryNodeRef(
            address=self._storage.get_root_address())

    def get(self, key):
        "get value for a key"
        #if tree is not locked by another writer
        #refresh the references and get new tree if needed
        if not self._storage.locked:
            self._refresh_tree_ref()
        #get the top level node
        node = self._follow(self._tree_ref)
        #traverse until you find appropriate node
        while node is not None:
            if key < node.key:
                node = self._follow(node.left_ref)
            elif key > node.key:
                node = self._follow(node.right_ref)
            else:
                return self._follow(node.value_ref)
        raise KeyError

    def set(self, key, value):
        "set a new value in the tree. will cause a new tree"
        #try to lock the tree. If we succeed make sure
        #we dont lose updates from any other process
        if self._storage.lock():
            self._refresh_tree_ref()
        #get current top-level node and make a value-ref
        node = self._follow(self._tree_ref)
        value_ref = ValueRef(value)
        #insert and get new tree ref
        self._tree_ref = self._insert(node, key, value_ref)


    def _insert(self, node, key, value_ref):
        "insert a new node creating a new path from root"
        #create a tree ifnthere was none so far
        if node is None:
            new_node = BinaryNode(
                BinaryNodeRef(), key, value_ref, BinaryNodeRef())
        elif key < node.key:
            new_node = BinaryNode.from_node(
                node,
                left_ref=self._insert(
                    self._follow(node.left_ref), key, value_ref))
        elif key > node.key:
            new_node = BinaryNode.from_node(
                node,
                right_ref=self._insert(
                    self._follow(node.right_ref), key, value_ref))
        else: #create a new node to represent this data
            new_node = BinaryNode.from_node(node, value_ref=value_ref)
        return BinaryNodeRef(referent=new_node)

    # delete functionality will not be available for red black trees
    # for symmetry remove it from unbalanced binary search tree
    # def delete(self, key):
    #     "delete node with key, creating new tree and path"
    #     if self._storage.lock():
    #         self._refresh_tree_ref()
    #     node = self._follow(self._tree_ref)
    #     self._tree_ref = self._delete(node, key)

    # def _delete(self, node, key):
    #     "underlying delete implementation"
    #     if node is None:
    #         raise KeyError
    #     elif key < node.key:
    #         new_node = BinaryNode.from_node(
    #             node,
    #             left_ref=self._delete(
    #                 self._follow(node.left_ref), key))
    #     elif key > node.key:
    #         new_node = BinaryNode.from_node(
    #             node,
    #             right_ref=self._delete(
    #                 self._follow(node.right_ref), key))
    #     else:
    #         left = self._follow(node.left_ref)
    #         right = self._follow(node.right_ref)
    #         if left and right:
    #             replacement = self._find_max(left)
    #             left_ref = self._delete(
    #                 self._follow(node.left_ref), replacement.key)
    #             new_node = BinaryNode(
    #                 left_ref,
    #                 replacement.key,
    #                 replacement.value_ref,
    #                 node.right_ref,
    #             )
    #         elif left:
    #             return node.left_ref
    #         else:
    #             return node.right_ref
    #     return BinaryNodeRef(referent=new_node)

    def _follow(self, ref):
        "get a node from a reference"
        #calls BinaryNodeRef.get
        return ref.get(self._storage)

    def _find_max(self, node):
        while True:
            next_node = self._follow(node.right_ref)
            if next_node is None:
                return node
            node = next_node

    # NEW METHOD 1
    def get_min(self):
        "get minimum value in a tree"
        node = self._follow(self._tree_ref)
        while True:
            next_node = self._follow(node.left_ref)
            if next_node is None:
                return self._follow(node.value_ref)
            node = next_node

    # NEW METHOD 2
    def get_left(self, key):
        "get key left of a key"
        #if tree is not locked by another writer
        #refresh the references and get new tree if needed
        if not self._storage.locked:
            self._refresh_tree_ref()
        #get the top level node
        node = self._follow(self._tree_ref)
        #traverse until you find appropriate node
        while node is not None:
            if key < node.key:
                node = self._follow(node.left_ref)
            elif key > node.key:
                node = self._follow(node.right_ref)
            else:
                node_left = self._follow(node.left_ref)
                return (node_left.key, self._follow(node_left.value_ref))
        raise KeyError

    # NEW METHOD 3
    def get_right(self, key):
        "get key right of a key"
        #if tree is not locked by another writer
        #refresh the references and get new tree if needed
        if not self._storage.locked:
            self._refresh_tree_ref()
        #get the top level node
        node = self._follow(self._tree_ref)
        #traverse until you find appropriate node
        while node is not None:
            if key < node.key:
                node = self._follow(node.left_ref)
            elif key > node.key:
                node = self._follow(node.right_ref)
            else:
                node_right = self._follow(node.right_ref)
                return (node_right.key, self._follow(node_right.value_ref))
        raise KeyError

    # NEW METHOD 4
    def traverse_in_order(self, node):
        "traverse the tree from a node returning visited nodes in a list"
        out_global = []
        def traverse_enclosed(node):
            if node is None:
                return
            traverse_enclosed(self._follow(node.left_ref))
            out_global.append((node.key, self._follow(node.value_ref)))
            traverse_enclosed(self._follow(node.right_ref))
        traverse_enclosed(node)
        return out_global

    # NEW METHOD 5
    def chop(self, chop_key):
        "get subtree left of a chop_key"
        "eg chopping on 4 returns all nodes with key <=4"
        # returns a list of key-vals with key's less than or equal to chop_key
        nodes_to_expand = []
        if not self._storage.locked:
            self._refresh_tree_ref()
        #get the top level node
        node = self._follow(self._tree_ref)
        #traverse until you find appropriate node
        while node is not None:
            parent_node = node
            if chop_key < node.key:
                node = self._follow(node.left_ref)
            elif chop_key > node.key:
                # take note any time we turn right. we will need to backtrack to these nodes
                if self._follow(node.right_ref) is not None:
                    nodes_to_expand.append(node)
                node = self._follow(node.right_ref)
            else:
                node = None
        # at this point parent_node stores our best approx position of chop_key in tree
        nodes_to_expand.append(parent_node)
        out = []
        # at parent node collect left subtree
        # then backtrack to all instances where we turned right
        for node in nodes_to_expand:
            if node.key<=chop_key:
                out.append((node.key, self._follow(node.value_ref)))
            out = out + self.traverse_in_order(self._follow(node.left_ref))
        return out

class Storage(object):
    SUPERBLOCK_SIZE = 4096
    INTEGER_FORMAT = "!Q"
    INTEGER_LENGTH = 8

    def __init__(self, f):
        self._f = f
        self.locked = False
        #we ensure that we start in a sector boundary
        self._ensure_superblock()

    def _ensure_superblock(self):
        "guarantee that the next write will start on a sector boundary"
        self.lock()
        self._seek_end()
        end_address = self._f.tell()
        if end_address < self.SUPERBLOCK_SIZE:
            self._f.write(b'\x00' * (self.SUPERBLOCK_SIZE - end_address))
        self.unlock()

    def lock(self):
        "if not locked, lock the file for writing"
        if not self.locked:
            portalocker.lock(self._f, portalocker.LOCK_EX)
            self.locked = True
            return True
        else:
            return False

    def unlock(self):
        if self.locked:
            self._f.flush()
            portalocker.unlock(self._f)
            self.locked = False

    def _seek_end(self):
        self._f.seek(0, os.SEEK_END)

    def _seek_superblock(self):
        "go to beginning of file which is on sec boundary"
        self._f.seek(0)

    def _bytes_to_integer(self, integer_bytes):
        return struct.unpack(self.INTEGER_FORMAT, integer_bytes)[0]

    def _integer_to_bytes(self, integer):
        return struct.pack(self.INTEGER_FORMAT, integer)

    def _read_integer(self):
        return self._bytes_to_integer(self._f.read(self.INTEGER_LENGTH))

    def _write_integer(self, integer):
        self.lock()
        self._f.write(self._integer_to_bytes(integer))

    def write(self, data):
        "write data to disk, returning the adress at which you wrote it"
        #first lock, get to end, get address to return, write size
        #write data, unlock <==WRONG, dont want to unlock here
        #your code here
        self.lock()
        self._seek_end()
        object_address = self._f.tell()
        self._write_integer(len(data))
        self._f.write(data)
        return object_address

    def read(self, address):
        self._f.seek(address)
        length = self._read_integer()
        data = self._f.read(length)
        return data

    def commit_root_address(self, root_address):
        self.lock()
        self._f.flush()
        #make sure you write root address at position 0
        self._seek_superblock()
        #write is atomic because we store the address on a sector boundary.
        self._write_integer(root_address)
        self._f.flush()
        self.unlock()

    def get_root_address(self):
        #read the first integer in the file
        #your code here
        self._seek_superblock()
        root_address = self._read_integer()
        return root_address

    def close(self):
        self.unlock()
        self._f.close()

    @property
    def closed(self):
        return self._f.closed

class DBDB(object):

    def __init__(self, f):
        self._storage = Storage(f)
        self._tree = BinaryTree(self._storage)

    def _assert_not_closed(self):
        if self._storage.closed:
            raise ValueError('Database closed.')

    def close(self):
        self._storage.close()

    def commit(self):
        self._assert_not_closed()
        self._tree.commit()

    def get(self, key):
        self._assert_not_closed()
        return self._tree.get(key)

    def set(self, key, value):
        self._assert_not_closed()
        return self._tree.set(key, value)

    def delete(self, key):
        self._assert_not_closed()
        return self._tree.delete(key)

    # NEW METHOD 1
    def get_min(self):
        self._assert_not_closed()
        return self._tree.get_min()

    # NEW METHOD 2
    def get_left(self, key):
        self._assert_not_closed()
        return self._tree.get_left(key)

    # NEW METHOD 3
    def get_right(self, key):
        self._assert_not_closed()
        return self._tree.get_right(key)

    # # NEW METHOD 4
    # def traverse_in_order_debugger(self):
    #     # don't do this for large trees!
    #     self._assert_not_closed()
    #     print self._tree.traverse_in_order(self._tree._follow(self._tree._tree_ref))

    # NEW METHOD 5
    def chop(self, chop_key):
        self._assert_not_closed()
        return self._tree.chop(chop_key)

def connect(dbname):
    try:
        f = open(dbname, 'r+b')
    except IOError:
        fd = os.open(dbname, os.O_RDWR | os.O_CREAT)
        f = os.fdopen(fd, 'r+b')
    return DBDB(f)


if __name__ == "__main__":
    #####################################
    # TEST EXAMPLES 1
    #####################################
    # an unbalanced stupid example
    db = connect("test4.dbdb")
    db.close()

    db = connect("test4.dbdb")
    db.set(16, "big")
    db.set(15, "med")
    db.set(14, "sml")
    db.commit()
    db.close()

    db = connect("test4.dbdb")
    assert db.get(16)=='big' # test get()
    assert db.get_min()=='sml' # test get_min()
    assert db.get_left(16)==(15, u'med') # test get_left()
    assert db.get_left(15)==(14, u'sml') # so the tree is indeed unbalanced
    assert db.chop(15.5)==[(15, u'med'), (14, u'sml')] # test chop is robust to whether the tree is balanced or not
    db.close()

    db = connect("test4.dbdb")
    db.set(16, "really big")
    db.close()

    db = connect("test4.dbdb")
    assert db.get(16)=='big' # test commit required for changes to be finalized
    db.close()

    #####################################
    # TEST EXAMPLES 2
    #####################################
    # a more complicated balanced example
    db = connect("test5.dbdb")
    db.close()

    db = connect("test5.dbdb")
    input_data = [
        (8,"eight"),
        (3,"three"),
        (10,"ten"),
        (1,"one"),
        (6,"six"),
        (14,"fourteen"),
        (4,"four"),
        (7,"seven"),
        (13,"thirteen"),
        ]
    for key, val in input_data:
        db.set(key, val)
    db.commit()
    db.close()

    db = connect("test5.dbdb")
    # db.traverse_in_order_debugger()
    # two ways to visualize the tree
    # (A) see diagram: https://en.wikipedia.org/wiki/Binary_search_tree
    # (B) use this helper function
    def print_children(key):
        try:
            print (key, 'left: ', db.get_left(key))
        except:
            print ('None')
        try:
            print (key, 'right: ', db.get_right(key))
        except:
            print ('None')
        print ('\n')
    # for key, val in input_data:
    #     print_children(key)

    # testing
    assert db.get_left(8)==(3,"three")
    assert db.get_right(8)==(10,"ten")
    assert db.get_left(3)==(1,"one")
    assert db.get_right(3)==(6,"six")
    assert db.get_left(6)==(4,"four")
    assert db.get_right(6)==(7,"seven")
    assert db.get_right(10)==(14,"fourteen")
    assert db.get_left(14)==(13,"thirteen") # ensure that we do match wikipedia
    assert db.chop(6)==[(3, u'three'), (1, u'one'), (6, u'six'), (4, u'four')] # test chop on key in database
    assert db.chop(6.1)==[(3, u'three'), (1, u'one'), (6, u'six'), (4, u'four')] # test chop on key out of database
    db.close()

    print ('success')

    # test locking
    # test unbalanced
    # test ordering
    # test duplicates
