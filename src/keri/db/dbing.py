# -*- encoding: utf-8 -*-
"""
keri.core.dbing module


import lmdb
db = lmdb.open("/tmp/keri_db_setup_test")
db.max_key_size()
511

# create named dbs  (core and tables)
    gDbEnv.open_db(b'core')
    gDbEnv.open_db(b'hid2did')  # table of dids keyed by hids
    gDbEnv.open_db(b'did2offer', dupsort=True)  # table of offer expirations keyed by offer relative dids
    gDbEnv.open_db(b'anon', dupsort=True)  # anonymous messages
    gDbEnv.open_db(b'expire2uid', dupsort=True)  # expiration to uid anon

The dupsort, integerkey, integerdup, and dupfixed parameters are ignored
if the database already exists.
The state of those settings are persistent and immutable per database.
See _Database.flags() to view the state of those options for an opened database.
A consequence of the immutability of these flags is that the default non-named
database will never have these flags set.

So only need to set dupsort first time opened each other opening does not
need to call it


May want to use buffers for reads of immutable serializations such as events
and sigs. Anything not read modify write but read only.

"{:032x}".format(1024)
'00000000000000000000000000000400'

h = ["00", "01", "02", "0a", "0f", "10", "1a", "11", "1f", "f0", "a0"]
h.sort()
h
['00', '01', '02', '0a', '0f', '10', '11', '1a', '1f', 'a0', 'f0']

l
['a', 'aa', 'b', 'ba', 'aaa', 'baa']
l.sort()
l
['a', 'aa', 'aaa', 'b', 'ba', 'baa']

"""
import os
import shutil
import tempfile

from contextlib import contextmanager

import lmdb

try:
    import simplejson as json
except ImportError:
    import json


from  ..kering import  KeriError

class DatabaseError(KeriError):
    """
    Database related errors
    Usage:
        raise DatabaseError("error message")
    """

def clearDatabaserDir(path):
    """
    Remove directory path
    """
    if os.path.exists(path):
        shutil.rmtree(path)



@contextmanager
def openDatabaser(name="test", cls=None):
    """
    Wrapper to enable temporary (test) Databaser instances
    When used in with statement calls .clearDirPath() on exit of with block

    Parameters:
        name is str name of temporary Databaser dirPath  extended name so
                 can have multiple temporary databasers is use differen name
        cls is Class instance of subclass instance

    Usage:

    with openDatabaser(name="gen1") as baser1:
        baser1.env  ....

    with openDatabaser(name="gen2, cls=Logger)

    """
    if cls is None:
        cls = Databaser
    try:
        databaser = cls(name=name, temp=True)

        yield databaser

    finally:

        databaser.clearDirPath()


class Databaser:
    """
    Databaser base class for LMDB instances.
    Creates a specific instance of an LMDB database directory and environment.

    Attributes:
        .name is LMDB database name did2offer
        .env is LMDB main (super) database environment
        .path is LMDB main (super) database directory path

    Properties:


    """
    HeadDirPath = "/var"  # default in /var
    TailDirPath = "keri/db"
    AltHeadDirPath = "~"  #  put in ~ when /var not permitted
    AltTailDirPath = ".keri/db"
    MaxNamedDBs = 16

    def __init__(self, headDirPath=None, name='main', temp=False):
        """
        Setup main database directory at .dirpath.
        Create main database environment at .env using .dirpath.

        Parameters:
            headDirPath is str head of the pathname of directory for main database
                If not provided use default headDirpath
            name is str pathname differentiator for directory for main database
                When system employs more than one keri databse name allows
                differentiating each instance by name
            temp is boolean If True then use temporary head pathname  instead of
                headDirPath if any or default headDirPath
        """
        self.name = name

        if temp:
            headDirPath = tempfile.mkdtemp(prefix="keri_lmdb_", suffix="_test", dir="/tmp")
            self.path = os.path.abspath(
                                os.path.join(headDirPath,
                                             self.TailDirPath,
                                             self.name))
            os.makedirs(self.path)

        else:
            if not headDirPath:
                headDirPath = self.HeadDirPath

            self.path = os.path.abspath(
                                os.path.expanduser(
                                    os.path.join(headDirPath,
                                                 self.TailDirPath,
                                                 self.name)))

            if not os.path.exists(self.path):
                try:
                    os.makedirs(self.path)
                except OSError as ex:
                    headDirPath = self.AltHeadDirPath
                    self.path = os.path.abspath(
                                        os.path.expanduser(
                                            os.path.join(headDirPath,
                                                         self.AltTailDirPath,
                                                         self.name)))
                    if not os.path.exists(self.path):
                        os.makedirs(self.path)
            else:
                if not os.access(self.path, os.R_OK | os.W_OK):
                    headDirPath = self.AltHeadDirPath
                    self.path = os.path.abspath(
                                        os.path.expanduser(
                                            os.path.join(headDirPath,
                                                         self.AltTailDirPath,
                                                         self.name)))
                    if not os.path.exists(self.path):
                        os.makedirs(self.path)

        # open lmdb major database instance
        # creates files data.mdb and lock.mdb in .dbDirPath
        self.env = lmdb.open(self.path, max_dbs=self.MaxNamedDBs)


    def clearDirPath(self):
        """
        Remove .dirPath
        """
        if self.env:
            try:
                self.env.close()
            except:
                pass

        if os.path.exists(self.path):
            shutil.rmtree(self.path)


    @staticmethod
    def dgKey(pre, dig):
        """
        Returns bytes DB key from concatenation of qualified Base64 prefix
        bytes pre and qualified Base64 str digest of serialized event
        """
        return (b'%s.%s' %  (pre, dig))

    @staticmethod
    def snKey(pre, sn):
        """
        Returns bytes DB key from concatenation of qualified Base64 prefix
        bytes pre and  int sn (sequence number) of event
        """
        return (b'%s.%032x' % (pre, sn))


    def putVal(self, db, key, val):
        """
        Write serialized bytes val to location key in db
        Overwrites existing val if any
        Returns True If val successfully written Else False

        Parameters:
            db is opened named sub db with dupsort=False
            key is bytes of key within sub db's keyspace
            val is bytes of value to be written
        """
        with self.env.begin(db=db, write=True, buffers=True) as txn:
            return (txn.put(key, val))


    def getVal(self, db, key):
        """
        Return val at key in db
        Returns None if no entry at key

        Parameters:
            db is opened named sub db with dupsort=False
            key is bytes of key within sub db's keyspace

        """
        with self.env.begin(db=db, write=False, buffers=True) as txn:
            return( txn.get(key))


    def delVal(self, db, key):
        """
        Deletes value at key in db.
        Returns True If key exists in database Else False

        Parameters:
            db is opened named sub db with dupsort=False
            key is bytes of key within sub db's keyspace
        """
        with self.env.begin(db=db, write=True, buffers=True) as txn:
            return (txn.delete(key))


    def putVals(self, db, key, vals):
        """
        Write each entry from list of bytes vals to key in db
        Adds to existing values at key if any
        Returns True If only one first written val in vals Else False

        Duplicates are inserted in lexocographic order not insertion order.
        Lmdb does not insert a duplicate unless it is a unique value for that
        key.

        Parameters:
            db is opened named sub db with dupsort=False
            key is bytes of key within sub db's keyspace
            vals is list of bytes of values to be written
        """
        with self.env.begin(db=db, write=True, buffers=True) as txn:
            result = True
            for val in vals:
                result = result and txn.put(key, val, dupdata=True)
            return result


    def getVals(self, db, key):
        """
        Return list of values at key in db
        Returns empty list if no entry at key

        Duplicates are retrieved in lexocographic order not insertion order.

        Parameters:
            db is opened named sub db with dupsort=True
            key is bytes of key within sub db's keyspace
        """

        with self.env.begin(db=db, write=False, buffers=True) as txn:
            cursor = txn.cursor()
            vals = []
            if cursor.set_key(key):  # moves to first_dup
                vals = [val for val in cursor.iternext_dup()]
            return vals


    def delVals(self,db, key, dupdata=True):
        """
        Deletes all values at key in db.
        Returns True If key exists in db Else False

        Parameters:
            db is opened named sub db with dupsort=True
            key is bytes of key within sub db's keyspace
        """
        with self.env.begin(db=db, write=True, buffers=True) as txn:
            return (txn.delete(key))


    def putIoVals(self, db, key, vals):
        """
        Write each entry from list of bytes vals to key in db in insertion order
        Adds to existing values at key if any
        Returns True If only one first written val in vals Else False

        Duplicates preserve insertion order.
        Because lmdb is lexocographic an insertion ordering value is prepended to
        all values that makes lexocographic order that same as insertion order
        Duplicates are ordered as a pair of key plus value so prepending prefix
        to each value changes duplicate ordering. Prefix is 7 characters long.
        With 6 character hex string followed by '.' for a max
        of 2**24 = 16,777,216 duplicates. With prepended ordinal must explicity
        check for duplicate values before insertion. Uses a python set for the
        duplicate inclusion test. Set inclusion scales with O(1) whereas list
        inclusion scales with O(n).

        Parameters:
            db is opened named sub db with dupsort=False
            key is bytes of key within sub db's keyspace
            vals is list of bytes of values to be written
        """
        dups = set(self.getIoVals(db, key))  #get preexisting dups if any
        with self.env.begin(db=db, write=True, buffers=True) as txn:
            cnt = 0
            cursor = txn.cursor()
            if cursor.set_key(key):
                cnt = cursor.count()
            result = True
            for val in vals:
                if val not in dups:
                    val = (b'%06x.' % (cnt)) +  val  # prepend ordering prefix
                    result = result and txn.put(key, val, dupdata=True)
                    cnt += 1
            return result


    def getIoVals(self, db, key):
        """
        Return list of values at key in db in insertion order
        Returns empty list if no entry at key

        Duplicates are retrieved in insertion order.
        Because lmdb is lexocographic an insertion ordering value is prepended to
        all values that makes lexocographic order that same as insertion order
        Duplicates are ordered as a pair of key plus value so prepending prefix
        to each value changes duplicate ordering. Prefix is 7 characters long.
        With 6 character hex string followed by '.' for a max
        of 2**24 = 16,777,216 duplicates,

        Parameters:
            db is opened named sub db with dupsort=True
            key is bytes of key within sub db's keyspace
        """

        with self.env.begin(db=db, write=False, buffers=True) as txn:
            cursor = txn.cursor()
            vals = []
            if cursor.set_key(key):  # moves to first_dup
                # slice off prepended ordering prefix
                vals = [val[7:] for val in cursor.iternext_dup()]
            return vals


    def getIoValsLast(self, db, key):
        """
        Return last added dup value at key in db in insertion order
        Returns None no entry at key

        Duplicates are retrieved in insertion order.
        Because lmdb is lexocographic an insertion ordering value is prepended to
        all values that makes lexocographic order that same as insertion order
        Duplicates are ordered as a pair of key plus value so prepending prefix
        to each value changes duplicate ordering. Prefix is 7 characters long.
        With 6 character hex string followed by '.' for a max
        of 2**24 = 16,777,216 duplicates,

        Parameters:
            db is opened named sub db with dupsort=True
            key is bytes of key within sub db's keyspace
        """

        with self.env.begin(db=db, write=False, buffers=True) as txn:
            cursor = txn.cursor()
            val = None
            if cursor.set_key(key):  # move to first_dup
                if cursor.last_dup(): # move to last_dup
                    val = cursor.value()[7:]  # slice off prepended ordering prefix
            return val


    def delIoVals(self,db, key, dupdata=True):
        """
        Deletes all values at key in db.
        Returns True If key exists in db Else False

        Parameters:
            db is opened named sub db with dupsort=True
            key is bytes of key within sub db's keyspace
        """
        with self.env.begin(db=db, write=True, buffers=True) as txn:
            return (txn.delete(key))



def openLogger(name="test"):
    """
    Returns contextmanager generated by openDatabaser but with Logger instance
    """
    return openDatabaser(name=name, cls=Logger)


class Logger(Databaser):
    """
    Logger sets up named sub databases with Keri Event Logs within main database

    Attributes:
        see superclass Databaser for inherited attributes

        .evts is named sub DB whose values are serialized events
            DB is keyed by identifer prefix plus digest of serialized event
            Only one value per DB key is allowed

        .dtss is named sub DB of datetime stamp strings in ISO 8601 format of
            the datetime when the event was first seen by log.
            Used for escrows timeouts and extended validation.
            DB is keyed by identifer prefix plus digest of serialized event
            Only one value per DB key is allowed

        .sigs is named sub DB of fully qualified event signatures
            DB is keyed by identifer prefix plus digest of serialized event
            More than one value per DB key is allowed

        .rcts is named sub DB of event receipt couplets. Each couplet is
            concatenation of fully qualified witness or validator prefix plus
            fully qualified event signature by witness or validator
            SB is keyed by identifer prefix plus digest of serialized event
            More than one value per DB key is allowed

        .kels is named sub DB of key event log tables that map sequence numbers
            to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed

        .pses is named sub DB of partially signed escrowed event tables
            that map sequence numbers to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed

        .ooes is named sub DB of out of order escrowed event tables
            that map sequence numbers to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed

        .dels is named sub DB of deplicitous event log tables that map sequence numbers
            to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed

        .ldes is named sub DB of likely deplicitous escrowed event tables
            that map sequence numbers to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed


    Properties:


    """
    def __init__(self, **kwa):
        """
        Setup named sub databases.

        Parameters:

        Notes:

        dupsort=True for sub DB means allow unique (key,pair) duplicates at a key.
        Duplicate means that is more than one value at a key but not a redundant
        copies a (key,value) pair per key. In other words the pair (key,value)
        must be unique both key and value in combination.
        Attempting to put the same (key,value) pair a second time does
        not add another copy.

        Duplicates are inserted in lexocographic order by value, insertion order.

        """
        super(Logger, self).__init__(**kwa)

        # Create by opening first time named sub DBs within main DB instance
        # Names end with "." as sub DB name must include a non Base64 character
        # to avoid namespace collisions with Base64 identifier prefixes.

        self.evts = self.env.open_db(key=b'evts.')
        self.dtss = self.env.open_db(key=b'dtss.')
        self.sigs = self.env.open_db(key=b'sigs.', dupsort=True)
        self.rcts = self.env.open_db(key=b'rcts.', dupsort=True)
        self.kels = self.env.open_db(key=b'kels.', dupsort=True)
        self.pses = self.env.open_db(key=b'pses.', dupsort=True)
        self.ooes = self.env.open_db(key=b'ooes.', dupsort=True)
        self.dels = self.env.open_db(key=b'dels.', dupsort=True)
        self.ldes = self.env.open_db(key=b'ldes.', dupsort=True)



    def putEvt(self, key, val):
        """
        Write serialized event bytes val to key
        Overwrites existing val if any
        Returns True If val successfully written Else False
        """
        return self.putVal(self.evts, key, val)


    def getEvt(self, key):
        """
        Return event at key
        Returns None if no entry at key
        """
        return self.getVal(self.evts, key)


    def delEvt(self, key):
        """
        Deletes value at key.
        Returns True If key exists in database Else False
        """
        return self.delVal(self.evts, key)


    def putDts(self, key, val):
        """
        Write serialized event datetime stamp val to key
        Overwrites existing val if any
        Returns True If val successfully written Else False
        """
        return self.putVal(self.dtss, key, val)


    def getDts(self, key):
        """
        Return datetime stamp at key
        Returns None if no entry at key
        """
        return self.getVal(self.dtss, key)


    def delDts(self, key):
        """
        Deletes value at key.
        Returns True If key exists in database Else False
        """
        return self.delVal(self.dtss, key)


    def getSigs(self, key):
        """
        Return list of signatures at key
        Returns empty list if no entry at key

        Duplicates are retrieved in lexocographic order not insertion order.
        """
        return self.getVals(self.sigs, key)


    def putSigs(self, key, vals):
        """
        Write each entry from list of bytes signatures vals to key
        Adds to existing signatures at key if any
        Returns True If no error

        Duplicates are inserted in lexocographic order not insertion order.
        """
        return self.putVals(self.sigs, key, vals)


    def getSigs(self, key):
        """
        Return list of signatures at key
        Returns empty list if no entry at key

        Duplicates are retrieved in lexocographic order not insertion order.
        """
        return self.getVals(self.sigs, key)


    def delSigs(self, key):
        """
        Deletes all values at key.
        Returns True If key exists in database Else False
        """
        return self.delVals(self.sigs, key)


    def putRcts(self, key, vals):
        """
        Write each entry from list of bytes receipt couplets vals to key
        Adds to existing receipts at key if any
        Returns True If no error

        Duplicates are inserted in lexocographic order not insertion order.
        """
        return self.putVals(self.rcts, key, vals)


    def getRcts(self, key):
        """
        Return list of receipt couplets at key
        Returns empty list if no entry at key

        Duplicates are retrieved in lexocographic order not insertion order.
        """
        return self.getVals(self.rcts, key)


    def delRcts(self, key):
        """
        Deletes all values at key.
        Returns True If key exists in database Else False
        """
        return self.delVals(self.rcts, key)


    def putKels(self, key, vals):
        """
        Write each entry from list of bytes vals to key
        Adds to existing event indexes at key if any
        Returns True If no error

        Duplicates are inserted in insertion order.
        """
        return self.putIoVals(self.kels, key, vals)


    def getKels(self, key):
        """
        Return list of receipt couplets at key
        Returns empty list if no entry at key

        Duplicates are retrieved in insertion order.
        """
        return self.getIoVals(self.kels, key)


    def getKelsLast(self, key):
        """
        Return last inserted dup event at key
        Returns None if no entry at key

        Duplicates are retrieved in insertion order.
        """
        return self.getIoValsLast(self.kels, key)


    def delKels(self, key):
        """
        Deletes all values at key.
        Returns True If key exists in database Else False
        """
        return self.delIoVals(self.kels, key)


    def putPses(self, key, vals):
        """
        Write each partial signed event entry from list of bytes vals to key
        Adds to existing event indexes at key if any
        Returns True If no error

        Duplicates are inserted in insertion order.
        """
        return self.putIoVals(self.pses, key, vals)


    def getPses(self, key):
        """
        Return list of partial signed event vals at key
        Returns empty list if no entry at key

        Duplicates are retrieved in insertion order.
        """
        return self.getIoVals(self.pses, key)


    def getPsesLast(self, key):
        """
        Return last inserted dup partial signed event at key
        Returns None if no entry at key

        Duplicates are retrieved in insertion order.
        """
        return self.getIoValsLast(self.pses, key)


    def delPses(self, key):
        """
        Deletes all values at key.
        Returns True If key exists in database Else False
        """
        return self.delIoVals(self.pses, key)



class Dupler(Databaser):
    """
    Dupler sets up named sub databases with Duplicitous Event Logs within main database

    Attributes:
        see superclass Databaser for inherited attributes

        .evts is named sub DB whose values are serialized events
            DB is keyed by identifer prefix plus digest of serialized event
            Only one value per DB key is allowed

        .dels is named sub DB of deplicitous event log tables that map sequence numbers
            to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed

        .pdes is named sub DB of potentially deplicitous escrowed event tables
            that map sequence numbers to serialized event digests.
            Values are digests used to lookup event in .evts sub DB
            DB is keyed by identifer prefix plus sequence number of key event
            More than one value per DB key is allowed


    Properties:


    """
    def __init__(self, **kwa):
        """
        Setup named sub databases.

        Parameters:

        """
        super(Dupler, self).__init__(**kwa)

        # create by opening first time named sub DBs within main DB instance
        # Names end with "." as sub DB name must include a non Base64 character
        # to avoid namespace collisions with Base64 identifier prefixes.
        # dupsort=True means allow duplicates for sn indexed

        self.evts = self.env.open_db(key=b'evts.')  #  open named sub db
        self.dels = self.env.open_db(key=b'dels.', dupsort=True)
        self.pdes = self.env.open_db(key=b'pdes.', dupsort=True)


