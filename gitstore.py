#!/usr/bin/env python

from log import *

from git import *
from gitdb import *
from git.objects.fun import *
from StringIO import *
import os
import sys
import pprint
from stat import *
from os.path import dirname, abspath, join

class GitStore (object):
    
    _base_path = None
    _logger = None
    file_mode = 0100644 
    dir_mode = 040000

    def __init__ (self):

        import config
        if not 'repo_basepath' in dir(config):
            raise Exception ("repo_basepath not found in config")

        PWD = dirname(abspath(__file__))
        self._base_path = os.path.join (PWD, config.repo_basepath)
        if not os.path.isdir (self._base_path):
            if 0 != os.system ('mkdir -p "%s"' % (self._base_path)):
                raise Exception ("cannot initial repo dir in '%s'" % (self._base_path))
        self._logger = Log ("main", config=config, base_path=PWD)

    def _throw_err (self, msg):
        assert msg
        self._logger.exception_ex (msg)
        raise Exception (msg)
    
    def _get_repo_path (self, repo_name):
        return os.path.join (self._base_path, repo_name)

    def _get_repo (self, repo_name):
        """on suc return opened repo obj, otherwise return None
           """
        repo_path = self._get_repo_path (repo_name)
        if not os.path.isdir (repo_path):
            self._throw_err ("repo '%s' not found" % (repo_name))
        repo = None
        try:
            repo = Repo (repo_path)
        except Exception, e:
            self._throw_err ("repo '%s' failed to open: %s" % (repo_name, str (e)))
        return repo

    def _get_branch (self, repo, branch_name):
        """ return branch's git.Object.ref
            """
        branch = None
        if not branch_name:
            return None
        try:
            branch = repo.branches[branch_name]
        except IndexError:
            return None
        return branch
    
    def _store_file (self, repo, tempfile):
        """ return new file's istream
            """
        assert repo
        st = os.stat (tempfile)
        temp_fp = open (tempfile, 'r')
        input = IStream ("blob", st.st_size, temp_fp)
        repo.odb.store (input)
        temp_fp.close ()
        return input

    def _store_tree (self, repo, entities):
        """return tree's istream
            """
        sio = StringIO ()
        tree_to_stream (entities, sio.write)
        sio.seek (0)
        t_stream = IStream ("tree", len(sio.getvalue ()), sio)
        repo.odb.store (t_stream)
        sio.close ()
        return t_stream

    def _create_path (self, repo, tree, path_segs, stream, is_file=True):
        assert path_segs
        item_name = path_segs[0]
        item_mode = None
        _stream = None
        entities = None
        if len (path_segs) > 1 or not is_file: #dir
            item_mode = self.dir_mode
        else:
            item_mode = self.file_mode
        if isinstance (tree, Tree):
            if len (path_segs) > 1: #dir
                if item_name in tree:
                    if not S_ISDIR (tree[item_name].mode): raise Exception ("oops") #the same name in tree is not dir
                    _stream = self._create_path (repo, tree[item_name], path_segs[1:], stream)
                else:
                    _stream = self._create_path (repo, None, path_segs[1:], stream)
            else: #file
                if item_name in tree and not S_ISREG (tree[item_name].mode): # the same name in tree is dir
                    raise Exception ("Oops")
                _stream = stream
            tree.cache.add (_stream.hexsha, item_mode, item_name, force=True)
            entities = tree._cache
        else:
            if len (path_segs) > 1: #dir
                _stream = self._create_path (repo, None, path_segs[1:], stream)
            else: #file
                _stream = stream
            entities = [ (_stream.binsha, item_mode, item_name) ]
        t_stream = self._store_tree (repo, entities)
        return t_stream
            

    def _do_commit (self, repo, head, tree_binsha, msg, parent=None):
        """ return new commit's hexsha, on error return None and output error
            """
        new_commit = Commit.create_from_tree (repo, Tree (repo, tree_binsha), msg, \
                            parent_commits=parent, head=False) 
        head.commit = new_commit #modify head's ref to commit
        return new_commit


    def create_repo (self, repo_name):
        """return hexsha of new repo's head
           """
        repo_path = self._get_repo_path (repo_name)
        if os.path.isdir (repo_path):
            self._throw_err ("repo '%s' already exists" % (repo_name))
        repo = None
        try:
            repo = Repo.init (repo_path, True, bare=True)
        except Exception, e:
            self._throw_err ("repo '%s' create error: %s" % (repo_name, str (e)))
        commit = None
        try:
            ts = self._store_tree (repo, [])
            commit = self._do_commit (repo, repo.head, ts.binsha, "create repo")
        except Exception, e:
            self._throw_err ("cannot create a initial commit in '%s': %s" % (repo_name, str (e)))
        return commit.hexsha

    def create_branch (self, repo_name, new_branch, from_branch='master'):
        """return hexsha of new repo's head
           """
        repo = self._get_repo (repo_name)
        _from = self._get_branch (repo, from_branch)
        if not _from:
            self._throw_err ("repo '%s' has no branch '%s'" % (repo_name, from_branch))
        if self._get_branch (repo, new_branch):
            self._throw_err ("repo '%s' already has branch '%s'" % (repo_name, new_branch))
        head = None
        try:
            head = Head.create (repo, new_branch, repo.branches[from_branch])
        except Exception, e: 
            self._throw_err ("repo '%s' cannot create branch '%s' from '%s'" % (repo_name, new_branch, from_branch))
        return head.commit.hexsha
    
    def ls_branches (self, repo_name):
        """return a dict, containing echo branch and its head hexsha
            """
        repo = self._get_repo (repo_name)
        result = dict ()
        for _branch in repo.branches:
             result[str(_branch)] = _branch.commit.hexsha
        return result
            
    def ls (self, repo_name):
        pass

    def log (self, repo_name, branch, path):
        pass

    def read (self, repo_name, branch, filename, version):
        pass

    def checkout (self, repo_name, branch, filename, version, tempfile):
        pass

    def store (self, repo_name, branch, filepath, tempfile):
        assert repo_name
        assert branch
        repo = self._get_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        tree_binsha = None
        try:
            path_segs = []
            _head = filepath
            while True:
                _head, _tail = os.path.split (_head)
                path_segs.insert (0, _tail)
                if not _head:
                    break
            
            f_stream = self._store_file (repo, tempfile) #store file content
            t_stream = self._create_path (repo, head.commit.tree, path_segs, f_stream)
            tree_binsha = t_stream.binsha
        except Exception, e:
            self._throw_err ("cannot store file '%s' into repo '%s': %s" % 
                    (filepath, repo_name, str (e)))
        commit = None
        try:
            commit = self._do_commit (repo, head, tree_binsha, "add file %s" % (filepath))
        except Exception, e:
            self._throw_err ("cannot create a new commit in '%s': %s" % (repo_name, str (e)))
        return commit.hexsha

# vim: set sw=4 ts=4 et :
