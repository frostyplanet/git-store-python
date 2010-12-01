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


def split_path (filepath):
    assert filepath
    path_segs = []
    _head = filepath
    while True:
        _head, _tail = os.path.split (_head)
        path_segs.insert (0, _tail)
        if not _head:
            break
    return path_segs

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
        assert isinstance (repo_name, str)
        return os.path.join (self._base_path, repo_name)

    def _get_repo (self, repo_name):
        """on suc return opened repo obj, otherwise return None
           """
        assert isinstance (repo_name, str)
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
        assert isinstance (branch_name, str)
        branch = None
        try:
            branch = repo.branches[branch_name]
        except IndexError:
            return None
        return branch

    def _get_commit (self, repo, rev):
        commit = None
        try:
            commit = repo.commit (rev)
        except BadObject, e:
            pass
        return commit
    
    def _store_file (self, repo, tempfile):
        """ return new file's istream
            """
        assert repo
        assert isinstance (tempfile, str)
        st = os.stat (tempfile)
        temp_fp = open (tempfile, 'r')
        input = IStream ("blob", st.st_size, temp_fp)
        repo.odb.store (input)
        temp_fp.close ()
        return input

    def _store_tree (self, repo, entities):
        """return tree's istream
            """
        assert repo
        sio = StringIO ()
        assert isinstance (entities, list)
        tree_to_stream (entities, sio.write)
        sio.seek (0)
        t_stream = IStream ("tree", len(sio.getvalue ()), sio)
        repo.odb.store (t_stream)
        sio.close ()
        return t_stream

    def _create_path (self, repo, tree, path_segs, stream, is_file=True):
        assert repo
        assert isinstance (path_segs, list)
        assert isinstance (stream, IStream)
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
        assert (repo)
        assert isinstance (head, HEAD) or isinstance (head, Head)
        assert msg != None
        new_commit = Commit.create_from_tree (repo, Tree (repo, tree_binsha), msg, \
                            parent_commits=parent, head=False) 
        head.commit = new_commit #modify head's ref to commit
        return new_commit

            
    def _ls_dir (self, repo, tree, basepath):
        """ return a list of filepath
            """
        assert (repo)
        assert isinstance (tree, Tree)
        assert isinstance (basepath, str)
        result = []
        for t in tree.trees:
            _result = self._ls_dir (repo, t, os.path.join (basepath, t.name))
            result.extend (_result)
        for b in tree.blobs:
            result.append (os.path.join (basepath, b.name))
        return result

    def _find_path (self, tree, path):
        assert isinstance (tree, Tree)
        assert path
        path_segs = split_path (path)
        path_item = path_segs[0]
        sub_tree = None
        try:
            sub_tree = tree[path_item]
        except: 
            pass
        if isinstance (sub_tree, Object):
            if len(path_segs) == 1:
                return sub_tree
            return self._find_path (sub_tree, str.join("/", path_segs[1:]))
        return None

    def create_repo (self, repo_name):
        """return hexsha of new repo's head
           """
        assert isinstance (repo_name, str)
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
        assert isinstance (repo_name, str)
        assert isinstance (new_branch, str)
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
        """return a dict, containing echo branch and its head commit hexSHA
            """
        assert isinstance (repo_name, str)
        repo = self._get_repo (repo_name)
        result = dict ()
        for _branch in repo.branches:
             result[str(_branch)] = _branch.commit.hexsha
        return result
            
    def ls (self, repo_name, branch='master'):
        """ list files in repo's branch, return a list containing filepath
            """
        assert isinstance (repo_name, str)
        assert isinstance (branch, str)
        result = list ()
        stack = list ()
        repo = self._get_repo (repo_name) 
        head = self._get_branch (repo, branch)
        if not head:
            self._throw_err ("repo '%s' has no branch '%s'" % (repo_name, branch))
        top_tree = head.commit.tree
        try:
            result = self._ls_dir (repo, top_tree, "")
        except Exception, e:
            self._throw_err ("ls repo '%s' branch '%s' error: %s" % (repo_name, branch, str(e)))
        return result

    def log (self, repo_name, version='HEAD', exclude_version=None, filepath=None):
        """ query the commit log, equal to 'git log version' or 'git log exclude_version..version'.
            version & exclude_version may be HEAD/branch/specified_rev, refer to gitrevisions(7) manpage.
            if file_path specified, just return the commits that have change to 'filepath'.
            commits that fits in will return in a list, each element will be a dict {'commit': ..., 'msg':..., 'author':..., 'date':AUTHOR_DATE }
            """
        assert isinstance (repo_name, str)
        assert isinstance (version, str)
        assert not exclude_version or isinstance (exclude_version, str)
        repo = self._get_repo (repo_name)
        if exclude_version:
            if not isinstance (self._get_commit (repo, exclude_version), Object):
                self._throw_err ("repo:%s has no revision %s" % (repo_name, exclude_version))
            rev_name = "%s..%s" % (exclude_version, version)
        else:
            rev_name = version
        result = []
        for commit in repo.iter_commits (rev_name, filepath):
            result.append ({
                    'commit': commit.hexsha,
                    'msg': commit.message,
                    'author_timestamp': commit.authored_date,
                    'author': commit.author.name,
                    })
        return result

    def read (self, repo_name, version, filename):
        """ version may be : HEAD/branch_name/specified_rev, refer to gitrevisions(7) manpage
            return file content
            """
        assert isinstance (repo_name, str)
        repo = self._get_repo (repo_name)
        commit = None
        if version:
            commit = self._get_commit (repo, version)
            if not commit:
                self._throw_err (" '%s' repo '%s' not exists" % (version, branch, repo_name))
        else:
            head = self._get_branch (repo, 'master')
            if not head:
                self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
            commit = head.commit
        file = None
        try:
            file = self._find_path (commit.tree, filename)
        except Exception, e:
            self._throw_err ("repo '%s' branch '%s' cannot get path '%s': %s"  % (repo_name, branch, filename, str(e)))
        if isinstance (file, Object):
            iostream = file.data_stream
            buf = iostream.read ()
            return buf
        self._throw_err ("repo '%s' branch '%s' has no path '%s'" % (repo_name, branch, filename))

    def checkout (self, repo_name, version, filename, tempfile):
        """ version may be : HEAD/branch_name/specified_commit
            returns nothing
            """
        assert isinstance (repo_name, str)
        buf = self.read (repo_name, version, filename)
        try:
            file = open (tempfile, "w+")
            file.write (buf)
            file.close ()
        except Exception, e:
            self._throw_err ("repo '%s' checkout '%s' of version '%s' error: %s" % (repo_name, filename, version, str(e)))

    def store (self, repo_name, branch, filepath, tempfile):
        """ return new commit version after store a file
            """
        assert isinstance (repo_name, str)
        assert isinstance (branch, str)
        repo = self._get_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        tree_binsha = None
        try:
            path_segs = split_path (filepath)
            f_stream = self._store_file (repo, tempfile) #store file content
            t_stream = self._create_path (repo, head.commit.tree, path_segs, f_stream)
            tree_binsha = t_stream.binsha
        except Exception, e:
            self._throw_err ("cannot store file '%s' into repo '%s': %s" % 
                    (filepath, repo_name, str (e)))
        commit = None
        try:
            commit = self._do_commit (repo, head, tree_binsha, "store file %s" % (filepath))
        except Exception, e:
            self._throw_err ("cannot create a new commit in '%s': %s" % (repo_name, str (e)))
        return commit.hexsha


# vim: set sw=4 ts=4 et :
