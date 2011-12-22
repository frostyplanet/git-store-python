#!/usr/bin/env python

import os
import sys
from log import Log

from git import Object, Tree, TreeModifier, Repo, Head, HEAD, Commit, BadObject
from gitdb import GitDB, IStream
from git.objects.fun import tree_to_stream
from StringIO import StringIO
import pprint
import stat
from os.path import dirname, abspath
import fcntl

def split_path (filepath):
    #TODO : check against invalid path
    assert filepath
    path_segs = []
    _head = filepath
    while True:
        _head, _tail = os.path.split (_head)
        path_segs.insert (0, _tail)
        if not _head:
            break
    return path_segs

def create_path_tree (path_obj_dict, expect_latest_version_dict=None):
    # if path_obj_dict 's value is None, means directory, otherwise is the file object of file content to be write
    root = {}
    for path, v in path_obj_dict.iteritems ():
        path_segs = split_path (path)
        t = root
        can_replace = True
        if expect_latest_version_dict:
            expect_latest_version = expect_latest_version_dict.get (path)
            if expect_latest_version == '':
                can_replace = False
        if len (path_segs) > 1:
            for seg in path_segs[0:-1]:
                if t.has_key (seg):
                    t = t[seg]
                else:
                    t[seg] = {}
                    t = t[seg]
        if v is None:
            t[path_segs[-1]] = None
        else:
            t[path_segs[-1]] = (v, can_replace)
    return root


class GitStore (object):
    
    _base_path = None
    _logger = None
    file_mode = 0100644 
    dir_mode = 040000
    _locker_dir_name = ".locker"
    _locker_path = None
    _locker_dict = None # to hold opened locker file's object

    def __init__ (self, need_lock=None):
        """ need_lock == 'file', create lockfile and use flock to prevent concurrent write,
        """
        import config
        if not 'repo_basepath' in dir(config):
            raise Exception ("repo_basepath not found in config")

        PWD = dirname(abspath(__file__))
        
        self._base_path = config.repo_basepath
        if not os.path.isabs (self._base_path):
            self._base_path = os.path.join (PWD, self._base_path)
        if not os.path.isdir (self._base_path):
            if 0 != os.system ('mkdir -p "%s"' % (self._base_path)):
                raise Exception ("cannot initial repo dir in '%s'" % (self._base_path))
        self._logger = Log ("cmfs", config=config)
        if need_lock == 'file':
            self._locker_path = os.path.join (self._base_path, self._locker_dir_name)
            if not os.path.exists (self._locker_path):
                os.makedirs (self._locker_path)
            self._locker_dict = dict ()
            self.lock_repo = self._lock_repo_file
            self.unlock_repo = self._unlock_repo_file
        else:
            self.lock_repo = self._fake_func
            self.unlock_repo = self._fake_func

    def _fake_func (self, *args):
        pass

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
        try:
            repo = Repo (repo_path, odbt=GitDB)
            return repo
        except Exception, e:
            self._throw_err ("repo '%s' failed to open: %s" % (repo_name, str (e)))

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
        """ return git.Object.Commit  speified by rev 
            """
        commit = None
        try:
            commit = repo.commit (rev)
        except BadObject, e:
            pass
        return commit
    
    def _store_blob (self, repo, fileobj):
        """ return new file's istream
            """
        assert repo
        assert isinstance (fileobj, file) or isinstance (fileobj, StringIO)
        fileobj.seek (0, 2)
        size = fileobj.tell ()
        fileobj.seek (0, 0)
        
        istream = IStream ("blob", size, fileobj)
        repo.odb.store (istream)
        return istream

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
    

    def _create_path_iter (self, repo, parent_tree, path_tree):
        entities = None
        if parent_tree is None:
            entities = []
        else:
            entities = parent_tree.cache
        def __add_entities (entities, hexsha, binsha, item_mode, item_name):
            if isinstance (entities, list):
                entities.append ((binsha, item_mode, item_name))
            else:
                entities.add (hexsha, item_mode, item_name, force=True)
            return
        for item_name in path_tree.keys ():
            obj = path_tree[item_name]
            cur_item = None
            try:
                if parent_tree is not None:
                    cur_item = parent_tree[item_name]
            except KeyError:
                pass
            if obj is None:
                if cur_item is None:
                    _istream = self._store_tree (repo, [])
                    __add_entities (entities, _istream.hexsha, _istream.binsha, self.dir_mode, item_name)
                else:
                    if not stat.S_ISDIR (cur_item.mode):
                        raise Exception ("Oops, '%s' is a file blocking path creation")
                    return None
                    # already exists, nothing to do
            elif isinstance (obj, dict):
                if cur_item is not None:
                    if not stat.S_ISDIR (cur_item.mode):
                        raise Exception ("Oops, '%s' is a file blocking path creation")
                _istream = self._create_path_iter (repo, cur_item, obj)
                if _istream is not None:
                    __add_entities (entities, _istream.hexsha, _istream.binsha, self.dir_mode, item_name)
            elif isinstance (obj, tuple): # obj is tuple
                (fileobj, can_replace) = obj
                if cur_item is not None:
                    if stat.S_ISREG (cur_item.mode):
                        if not can_replace:
                            raise Exception ("%s is already exists in target path" % (item_name)) # TODO what path?
                    else:
                        raise Exception ("Oops, '%s' is a directory blocking file creation")
                _istream = self._store_blob (repo, fileobj)
                __add_entities (entities, _istream.hexsha, _istream.binsha, self.file_mode, item_name)
        if parent_tree is not None:
            # entities is TreeCacheModifier
            entities.set_done ()
            entities = parent_tree._cache
        t_stream = self._store_tree (repo, entities)
        return t_stream


#    def _create_path (self, repo, tree, path_segs, fileobj, is_file=True, replace_file=True):
#        """ a recursive function.
#            if is_file is True, fileobj a opened python file object or StringIO object contains content to write  
#               if replace_file is False, will raise Exception when file already present.
#                   replace_file only effective when is_file is True,
#            if is_file is False, fileobj must be None, and will return None when directory path already exists
#                 """
#        # a recursive function
#        assert repo is not None
#        assert isinstance (path_segs, list)
#        assert not is_file or fileobj is not None
#        item_name = path_segs[0]
#        item_mode = None
#        _istream = None
#        entities = None
#        if isinstance (tree, Tree):
#            item = None
#            try:
#                item = tree[item_name]
#            except KeyError:
#                pass
#            if len (path_segs) > 1: # need to step into sub directory
#                if item is not None:
#                    item_mode = item.mode
#                    if not stat.S_ISDIR (item_mode):
#                        raise Exception ("Oops, '%s' is a file blocking path creation")
#                else:
#                    item_mode = self.dir_mode
#                _istream = self._create_path (repo, item, path_segs[1:], fileobj, is_file, replace_file)
#                if _istream is None:
#                    return None
#            else: 
#                if item is not None:
#                    item_mode = item.mode
#                    if is_file:
#                        if stat.S_ISDIR (item_mode):
#                            raise Exception ("Oops, target path exists but is a directory")
#                        if not replace_file:
#                            raise Exception ("target path already exists")
#                    else:
#                        if stat.S_ISREG (item_mode): 
#                            raise Exception ("Oops, target path exists but is not a directory")
#                        return None
#                else:
#                    if is_file:
#                        item_mode = self.file_mode
#                    else:
#                        item_mode = self.dir_mode
#                    # path already exists, do some checking
#                if is_file:
#                    _istream = self._store_blob (repo, fileobj) #store file content
#                    if item is not None:
#                        if _istream.hexsha == item.hexsha:
#                            return None #  already has the same file
#                else: 
#                    _istream = self._store_tree (repo, []) # create empty directory
#            # add tree-item to its parent
#            assert _istream is not None
#            tm = tree.cache
#            tm.add (_istream.hexsha, item_mode, item_name, force=True)
#            tm.set_done ()
#            entities = tree._cache
#        else:
#            if len (path_segs) > 1: # need to create sub-directory structure
#                _istream = self._create_path (repo, None, path_segs[1:], fileobj, is_file, replace_file)
#                item_mode = self.dir_mode
#            else: 
#                if is_file:
#                    _istream = self._store_blob (repo, fileobj) #store file content
#                    item_mode = self.file_mode
#                else: 
#                    _istream = self._store_tree (repo, []) # create empty directory
#                    item_mode = self.dir_mode
#            assert _istream is not None
#            entities = [ (_istream.binsha, item_mode, item_name) ]
#        t_stream = self._store_tree (repo, entities)
#        return t_stream

    def _delete_path (self, repo, tree, path_segs):
        # a recursive function
        assert repo is not None
        assert isinstance (path_segs, list)
        assert isinstance (tree, Tree)
        assert path_segs
        item_name = path_segs[0]
        _istream = None
        entities = None
        try:
            item = tree[item_name]
        except KeyError:
            return None
        if len (path_segs) > 1: # need to recurse down to sub directory
            _istream = self._delete_path (repo, item, path_segs[1:])
            if _istream is None:
                return None
            tm = tree.cache
            tm.add (_istream.hexsha, item.mode, item_name, force=True)
            tm.set_done ()
            entities = tree._cache
        else: # len (path_segs) == 1
            # delete tree-item from its parent, so we copy all entities except the one we want to delete
            entities = []
            for b in tree.blobs:
                if b.name == item_name: 
                    continue
                entities.append ((b.binsha, b.mode, b.name,))
            for t in tree.trees:
                if t.name == item_name:
                    continue
                entities.append ((t.binsha, t.mode, t.name,))
        t_stream = self._store_tree (repo, entities)
        return t_stream
          

    def _do_commit (self, repo, head, tree_binsha, msg, parent=None):
        """ if parent parameter is None, we make it default to be [head.commit]
            
            return new commit's hexsha, on error return None and output error
            """
        assert (repo)
        assert head is None or isinstance (head, HEAD) or isinstance (head, Head)
        assert msg != None
        if parent is None:
            try:
                parent = [head.commit]
            except ValueError:
                pass
        new_commit = Commit.create_from_tree (repo, Tree (repo, tree_binsha), msg, \
                            parent_commits=parent, head=False) # because the first commit has no parent, parameter head==True likely fails
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
            if _result:
                result.extend (_result)
            else:
                result.append (basepath.rstrip ("/") + "/")
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

    def create_repo (self, repo_name, msg=None):
        """return hexsha of new repo's head
           """
        assert isinstance (repo_name, str)
        self.lock_repo (repo_name)
        repo_path = self._get_repo_path (repo_name)
        if os.path.isdir (repo_path):
            self.unlock_repo (repo_name)
            self._throw_err ("repo '%s' already exists" % (repo_name))
        repo = None
        try:
            repo = Repo.init (repo_path, True, bare=True)
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("repo '%s' create error: %s" % (repo_name, str (e)))
        commit = None
        try:
            ts = self._store_tree (repo, [])
            if msg:
                commit_msg = msg
            else:
                commit_msg = "create repo"
            commit = self._do_commit (repo, repo.head, ts.binsha, commit_msg)
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot create a initial commit in '%s': %s" % (repo_name, str (e)))
        self.unlock_repo (repo_name)
        return commit.hexsha

    def create_branch (self, repo_name, new_branch, from_revision='master'):
        """return hexsha of new repo's head
           """
        assert isinstance (repo_name, str)
        assert isinstance (new_branch, str)
        repo = self._get_repo (repo_name)
        self.lock_repo (repo_name)
        _from = self._get_commit (repo, from_revision)
        if not _from:
            self.unlock_repo (repo_name)
            self._throw_err ("repo '%s' has no revision '%s'" % (repo_name, from_revision))
        if self._get_branch (repo, new_branch):
            self.unlock_repo (repo_name)
            self._throw_err ("repo '%s' already has branch '%s'" % (repo_name, new_branch))
        head = None
        try:
            head = Head.create (repo, new_branch, _from)
        except Exception, e: 
            self.unlock_repo (repo_name)
            self._throw_err ("repo '%s' cannot create branch '%s' from '%s', %s" % (repo_name, new_branch, from_revision, str(e)))
        self.unlock_repo (repo_name)
        return head.commit.hexsha

    def delete_branch (self, repo_name, branch):
        """ returns nothing after delete a branch
            """
        assert isinstance (repo_name, str)
        assert isinstance (branch, str)
        repo = self._get_repo (repo_name)
        self.lock_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self.unlock_repo (repo_name)
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        try:
            repo.delete_head(head, force=True)
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot delete '%s' in repo '%s': %s" % 
                    (branch, repo_name, str (e)))
        self.unlock_repo (repo_name)

    def ls_repos (self):
        """return a list of repo_name"""
        l = os.listdir (self._base_path)
        if self._locker_dir_name in l:
            l.remove (self._locker_dir_name)
        return l
    
    def ls_branches (self, repo_name):
        """return a dict, containing echo branch and its head commit hexSHA
            """
        assert isinstance (repo_name, str)
        repo = self._get_repo (repo_name)
        result = dict ()
        for _branch in repo.branches:
            result[str(_branch)] = _branch.commit.hexsha
        return result

    def ls_head(self, repo_name, branch):
        """return head hexsha string of the branch"""
        assert isinstance (repo_name, str)
        assert isinstance (branch, str)
        repo = self._get_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        return head.commit.hexsha
            
    def ls (self, repo_name, version='HEAD'):
        """ list files in repo's branch, return a list containing filepath
            """
        assert isinstance (repo_name, str)
        assert isinstance (version, str)
        result = list ()
        repo = self._get_repo (repo_name) 
        commit = self._get_commit (repo, version)
        if not isinstance (commit, Object):
            self._throw_err ("repo '%s' has no revision '%s'" % (repo_name, version))
        top_tree = commit.tree
        try:
            result = self._ls_dir (repo, top_tree, "")
        except Exception, e:
            self._throw_err ("ls repo '%s' revision '%s' error: %s" % (repo_name, version, str(e)))
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
        # if revision not exist, iter_commits will give empty result, so we check first 
        if not isinstance (self._get_commit (repo, version), Object):
            self._throw_err ("repo:%s has no revision %s" % (repo_name, version))
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
                self._throw_err (" '%s' repo '%s' not exists" % (repo_name, version))
        else:
            head = self._get_branch (repo, 'master')
            if not head:
                self._throw_err ("version '%s' of repo '%s' not exists" % (version, repo_name))
            commit = head.commit
        f = None
        try:
            f = self._find_path (commit.tree, filename)
        except Exception, e:
            self._throw_err ("repo '%s' version '%s' cannot get path '%s': %s"  % (repo_name, version, filename, str(e)))
        if not isinstance (f, Object):
            self._throw_err ("repo '%s' version '%s' has no path '%s'" % (repo_name, version, filename))
        try:
            ostream = f.data_stream
            buf = ostream.read ()
            return buf
        except Exception, e:
            self._throw_err ("repo '%s' version '%s' '%s' read error, %s" % (repo_name, version, filename, str(e)))

    def checkout (self, repo_name, version, filename, tempfile):
        """ version may be : HEAD/branch_name/specified_commit
            returns nothing
            """
        assert isinstance (repo_name, str)
        buf = self.read (repo_name, version, filename)
        f = None
        try:
            f = open (tempfile, "w+")
        except Exception, e:
            self._throw_err ("repo '%s' checkout '%s' of version '%s' error: %s" % (repo_name, filename, version, str(e)))
        try:
            f.write (buf)
            f.close ()
        except Exception, e:
            f.close ()
            self._throw_err ("repo '%s' checkout '%s' of version '%s' error: %s" % (repo_name, filename, version, str(e)))

    def _latest_commit (self, repo, branch, filepath):
        _iter = repo.iter_commits (branch, filepath)
        try:
            cur_version = _iter.next ()
            return cur_version
        except StopIteration:
            return None

    def get_latest_commit (self, repo_name, branch, filepath):
        assert isinstance (repo_name, basestring)
        assert isinstance (branch, basestring)
        repo = self._get_repo (repo_name)
        _commit = self._latest_commit (repo, branch, filepath)
        return _commit.hexsha

    def store (self, repo_name, branch, path, content, expect_latest_version=None, msg=None):
        si = StringIO (content)
        val = None
        try:
            val = self.store_file (repo_name, branch, {path:si}, expect_latest_version_dict={path:expect_latest_version}, msg=msg)
        finally:
            si.close ()
        return val
            
    def store_file (self, repo_name, branch, path_obj_dict, expect_latest_version_dict=None, msg=None):
        """ 
            both path_obj_dict and expect_latest_version_dict 's key is filepath
            path_obj_dict's value can be file object or StringIO object, contain the content to be writen, you will need to close it youself alfterware.
            expect_latest_version_dict 's value : empty string '' means only store into the branch when no such a file in it , 
                    non-empty string means only store into the branch when the file's latest version match,
                    None means always replace.
            return new commit version after store a file, if the file is the same with the branch's head, return None
            """
        assert isinstance (repo_name, basestring)
        assert isinstance (branch, basestring)
        if len (path_obj_dict) == 0:
            return
        repo = self._get_repo (repo_name)
        self.lock_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self.unlock_repo (repo_name)
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        if isinstance (expect_latest_version_dict, dict):
            for path, expect_latest_version in expect_latest_version_dict.iteritems ():
                if not expect_latest_version:
                    continue
                _cur_commit = self._latest_commit (repo, branch, path)
                if _cur_commit is None:
                    self.unlock_repo (repo_name)
                    self._throw_err ("file has no history, maybe the repo is corrupted")
                if _cur_commit.hexsha != expect_latest_version:
                    self.unlock_repo (repo_name)
                    self._throw_err ("file has been update by others, new version is %s" % (_cur_commit.hexsha))
        new_tree_binsha = None
        old_tree = head.commit.tree
        if len (path_obj_dict) <= 3:
            files = "file:" + ", ".join (map (lambda x:"'" + x + "'", path_obj_dict.keys ()))
        else:
            files = "%d files" % (len(path_obj_dict))
        try:
            path_tree = create_path_tree (path_obj_dict, expect_latest_version_dict)
            assert path_tree
            t_stream = self._create_path_iter (repo, old_tree, path_tree)
            new_tree_binsha = t_stream.binsha
            if new_tree_binsha == old_tree.binsha: # the same as before
                self.unlock_repo (repo_name)
                return None
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot store file %s into repo '%s': %s" % 
                    (files, repo_name, str (e)))
        commit = None
        try:
            if msg:
                commit_msg = msg
            else:
                commit_msg = "store %s" % (files) 
            commit = self._do_commit (repo, head, new_tree_binsha, commit_msg)
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot create a new commit in '%s': %s" % (repo_name, str (e)))
        self.unlock_repo (repo_name)
        return commit.hexsha

    def mkdir (self, repo_name, branch, path, msg=None):
        assert isinstance (repo_name, basestring)
        assert isinstance (branch, basestring)
        repo = self._get_repo (repo_name)
        self.lock_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self.unlock_repo (repo_name)
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        new_tree_binsha = None
        old_tree = head.commit.tree
        try:
            path_tree = create_path_tree ({path:None})
            t_stream = self._create_path_iter (repo, old_tree, path_tree)
            new_tree_binsha = t_stream.binsha
            if new_tree_binsha == old_tree.binsha: # the same as before
                self.unlock_repo (repo_name)
                return None
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot mkdir '%s' into repo '%s': %s" % 
                    (path, repo_name, str (e)))

        commit = None
        try:
            if msg:
                commit_msg = msg
            else:
                commit_msg = "mkdir %s" % (path)
            commit = self._do_commit (repo, head, new_tree_binsha, commit_msg)
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot create a new commit in '%s': %s" % (repo_name, str (e)))
        self.unlock_repo (repo_name)
        return commit.hexsha


    def delete (self, repo_name, branch, path, msg=None):
        """ if deleted the path, return new commit hexsha. if the path is not existing , return None  """
        assert isinstance (repo_name, basestring)
        assert isinstance (branch, basestring)
        repo = self._get_repo (repo_name)
        self.lock_repo (repo_name)
        head = self._get_branch (repo, branch)
        if not head:
            self.unlock_repo (repo_name)
            self._throw_err ("branch '%s' of repo '%s' not exists" % (branch, repo_name))
        tree_binsha = None
        try:
            path_segs = split_path (path)
            _istream = self._delete_path (repo, head.commit.tree, path_segs)
            if _istream is None:
                self.unlock_repo (repo_name)
                return None
            tree_binsha = _istream.binsha
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot delete '%s' from repo '%s' ref '%s': %s" % 
                    (path, repo_name, branch, str (e)))
        try:
            if msg:
                commit_msg = msg
            else:
                commit_msg = "delete %s" % (path)
            commit = self._do_commit (repo, head, tree_binsha, commit_msg)
        except Exception, e:
            self.unlock_repo (repo_name)
            self._throw_err ("cannot create a new commit in '%s': %s" % (repo_name, str (e)))
        self.unlock_repo (repo_name)
        return commit.hexsha


    def _lock_repo_file (self, repo_name):
        """ the lock created is advisory lock between processes, so it will not be effective between threads """
        try:
            f = open (os.path.join (self._locker_path, repo_name), "w")
        except IOError, e:
            self._throw_err ("cannot open lock file for %s, %s" % (repo_name, str(e)))
        self._locker_dict[repo_name] = f
        try:
            fcntl.flock (f.fileno (), fcntl.LOCK_EX)
        except Exception, e:
            self._throw_err ("cannot create lock for %s, %s" % (repo_name, str(e)))
        
    def _unlock_repo_file (self, repo_name):
        if self._locker_dict.has_key (repo_name):
            self._locker_dict[repo_name].close ()
            del self._locker_dict[repo_name]

        
        
# vim: set sw=4 ts=4 et :
