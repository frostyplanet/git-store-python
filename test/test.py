#!/usr/bin/env python

import os
import sys
import string
import re
from os.path import dirname, abspath, join
import unittest

reload(sys)
sys.setdefaultencoding("utf-8")
PWD = dirname(abspath(__file__))
sys.path.append(os.path.join (PWD, ".."))

from gitstore import *
import config


def _get_md5 (f):
    import subprocess
    p = subprocess.Popen (["md5sum", f], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output,err = p.communicate ()
    if err: return None
    arr = re.split ("\s+", output)
    if arr: return arr[0]
    return None

class TestGitStore (unittest.TestCase):

    def setUp (self):
        self.gs = GitStore ()
        if config.repo_basepath:
            os.system ("rm -rvf %s/*" % (config.repo_basepath))


    def _checkout (self, repo_name, version, filepath, orgfile):
        tempfile = "/tmp/foo"
        self.gs.checkout (repo_name, version, filepath, tempfile)
        md51 = _get_md5 (tempfile)
        md52 = _get_md5 (orgfile)
        print "compare", repo_name, filepath, version, tempfile, orgfile
        print "got", md51, md52
        assert md51 == md52
        if os.path.isfile (tempfile): 
            os.unlink (tempfile)

    def store (self, repo_name, branch_name, path, temppath, expect_latest_version=None):
        f = open (temppath, "r")
        commit = None
        try:
            commit = self.gs.store (repo_name, branch_name, path, f, expect_latest_version)
        finally:
            f.close()
        return commit

    def test_repo_branch (self):
        print "test repo create:"
        master_head = self.gs.create_repo ("unit_test")
        repo = self.gs._get_repo ("unit_test")
        assert repo
        print "ok"
        print "test list branches:"
        branches = self.gs.ls_branches ("unit_test")
        pprint.pprint (branches)
        assert len (branches) == 1
        assert branches["master"] == master_head 
        print "ok"
        print "store file into master:"
        new_head = self.store ("unit_test", "master", "testfile", "test/test_file")
        assert new_head
        print "create branch1:"
    #    self.gs.create_branch ("unit_test", "branch2", "branch1")
        branch_head = self.gs.create_branch ("unit_test", "branch1")
    #    self.gs.create_branch ("unit_test", "branch1", "master")
        branches = self.gs.ls_branches ("unit_test")
        self.gs.create_branch ("unit_test", "branch2", "branch1")
        pprint.pprint (branches)
        assert len (branches) == 2
        print "store test_file2 into branch1:"
        branch1_head = self.store ("unit_test", "branch1", "haha/haha/testfile", "test/test_file2")
        assert branch_head != branch1_head 
        master_head = self.store ("unit_test", "master", "haha/testfile", "test/test_file")
        print "store test_file into master:"
        branches = self.gs.ls_branches ("unit_test")
        assert branches["master"] == master_head
        assert branches["branch1"] == branch1_head
        pprint.pprint (branches)
        print "ls unit_test:branch1"
        print self.gs.ls ("unit_test", "branch1")
        print "store test_file2 into master"
        master_head_new = self.store ("unit_test", "master", "haha/testfile", "test/test_file2")
        print "master has advanced to ", master_head_new
        print "test ls_head"
        assert self.gs.ls_head('unit_test', 'master') == master_head_new
        print "checkout master"
        self._checkout ('unit_test', master_head, "haha/testfile", "test/test_file")
        self._checkout ('unit_test', master_head_new, "haha/testfile", "test/test_file2")
        self._checkout ("unit_test", branch1_head, "haha/haha/testfile", "test/test_file2")
        print "test delete branch1"
        self.gs.delete_branch('unit_test', 'branch1')
        branches = self.gs.ls_branches ("unit_test")
        print "check branch1 been deleted"
        assert 'branch1' not in branches
        self.gs.delete_branch('unit_test', 'branch2')
        branches = self.gs.ls_branches ("unit_test")
        print "check branch2 been deleted"
        assert 'branch2' not in branches

    def test_store_file_and_directory (self):
        master_head = self.gs.create_repo ("unit_test")
        repo = self.gs._get_repo ("unit_test")
        self.assert_ (repo)
        assert repo
        v1 = self.store ("unit_test", "master", "haha/test/file", "test/test_file")
        self.assert_ (v1)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/test/file"])

        print "* test store file into the same dir"
        v2 = self.store ("unit_test", "master", "haha/test/file_copy", "test/test_file")
        self.assert_ (v2)
        self.assert_ (v2 != v1)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/test/file", "haha/test/file_copy"])

        print "* store the same file into the same place, should not increase version"
        v2_1 = self.store ("unit_test", "master", "haha/test/file", "test/test_file")
        self.assert_ (not v2_1)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/test/file", "haha/test/file_copy"])

        print "* test mkdir which exists"
        v2_2 = self.gs.mkdir ("unit_test", "master", "haha/test")
        self.assert_ (not v2_2)
        print "* test mkdir"
        v3 = self.gs.mkdir ("unit_test", "master", "haha/test2")
        print self.gs.ls ("unit_test", "master")
        print "* test mkdir on a existing path"
        try:
            self.gs.mkdir ("unit_test", "master", "haha/test/file")
            self.fail ("expect exception, but get nonthing")
        except Exception, e:
            print "catch expect exception", str(e)
        try:
            self.gs.mkdir ("unit_test", "master", "haha/test/file/file")
            self.fail ("expect exception, but get nonthing")
        except Exception, e:
            print "catch expect exception", str(e)
        print "* test store file block by a existing directory"
        try:
            self.store ("unit_test", "master", "haha/test2", "test/test_file")
            self.fail ("expect exception, but get nonthing")
        except Exception, e:
            print "catch expect exception", str(e)

    def test_version_checking_when_store (self):
        master_head = self.gs.create_repo ("unit_test")
        repo = self.gs._get_repo ("unit_test")
        self.assert_ (repo)
        assert repo
        v1 = self.store ("unit_test", "master", "haha/file", "test/test_file")
        self.assert_ (v1)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/file"])

        v2 = self.store ("unit_test", "master", "haha/file_copy", "test/test_file")
        self.assert_ (v2)
        self.assert_ (v2 != v1)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/file", "haha/file_copy"])

        print "* test file latest commit"
        v1_2 = self.gs.get_latest_commit ("unit_test", "master", "haha/file")
        self.assertEqual (v1_2, v1)

        print "* update haha/file, expect_last_version = %s, should be ok" % (v1_2)
        v3 = self.store ("unit_test", "master", "haha/file", "test/test_file2", v1_2)
        self.assert_ (v3 and v3 != v2)
        print "* test version checking, should raise Exception"
        si = StringIO ()
        si.write ("asdfsdf what ever")
        try:
            self.gs.store ("unit_test", "master", "haha/file", si, expect_latest_version=v1)
            self.fail ("expect exception, but get nonthing")
        except Exception, e:
            print "catch expect exception", str(e)

    def test_delete (self):
        master_head = self.gs.create_repo ("unit_test")
        repo = self.gs._get_repo ("unit_test")
        self.assert_ (repo)
        assert repo
        v1 = self.store ("unit_test", "master", "haha/file", "test/test_file")
        self.assert_ (v1)
        v2 = self.store ("unit_test", "master", "haha/file2", "test/test_file")
        self.assert_ (v2)
        b1 = self.gs.create_branch ("unit_test", "b1")
        self.assertEqual (v2, b1)
        b2 = self.store ("unit_test", "b1", "file3", "test/test_file")
        self.assertEqual (self.gs.ls ("unit_test", "b1"), ["haha/file", "haha/file2", "file3"])
        self.assert_ (b2)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/file", "haha/file2"])
        v3 = self.gs.delete ("unit_test", "master", "haha/file")
        self.assert_ (v3)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["haha/file2"])
        v4 = self.gs.delete ("unit_test", "master", "haha")
        self.assert_ (v4)
        self.assertEqual (self.gs.ls ("unit_test", "master"), [])
        self.assertEqual (self.gs.ls ("unit_test", "b1"), ["haha/file", "haha/file2", "file3"])
        v5 = self.store ("unit_test", "master", "file4", "test/test_file2")
        self.assert_ (v5)
        b3 = self.gs.delete ("unit_test", "b1", "file3")
        self.assert_ (b3)
        self.assertEqual (self.gs.ls ("unit_test", "b1"), ["haha/file", "haha/file2"])
        print "* test delete non-existing file, should return None"
        b4 = self.gs.delete ("unit_test", "b1", "file3")
        self.assert_ (not b4)
        self.assertEqual (self.gs.ls ("unit_test", "master"), ["file4"])

        


if __name__ == '__main__':
    unittest.main ()

# vim: set sw=4 ts=4 et :
