#!/usr/bin/env python

import os
import sys
import string
import re
from os.path import dirname, abspath, join

reload(sys)
sys.setdefaultencoding("utf-8")
PWD = dirname(abspath(__file__))
sys.path.append(os.path.join (PWD, ".."))

from gitstore import *

def test_repo_create (gs):
    print "test repo create:"
    master_head = gs.create_repo ("unit_test")
    repo = gs._get_repo ("unit_test")
    assert repo
    print "ok"
    print "test list branches:"
    branches = gs.ls_branches ("unit_test")
    pprint.pprint (branches)
    assert len (branches) == 1
    assert branches["master"] == master_head 
    print "ok"
    print "store file into master:"
    new_head = gs.store ("unit_test", "master", "testfile", "test/test_file")
    assert new_head

def _get_md5 (file):
    import subprocess
    p = subprocess.Popen (["md5sum", file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output,err = p.communicate ()
    if err: return None
    arr = re.split ("\s+", output)
    if arr: return arr[0]
    return None

def test_checkout (repo_name, version, filepath, orgfile):
    tempfile = "/tmp/foo"
    gs.checkout (repo_name, version, filepath, tempfile)
    md51 = _get_md5 (tempfile)
    md52 = _get_md5 (orgfile)
    print "compare", repo_name, filepath, version, tempfile, orgfile
    print "got", md51, md52
    assert md51 == md52
    if os.path.isfile (tempfile): os.unlink (tempfile)

def test_branch ():
    print "create branch1:"
#    gs.create_branch ("unit_test", "branch2", "branch1")
    branch_head = gs.create_branch ("unit_test", "branch1")
#    gs.create_branch ("unit_test", "branch1", "master")
    branches = gs.ls_branches ("unit_test")
    gs.create_branch ("unit_test", "branch2", "branch1")
    pprint.pprint (branches)
    assert len (branches) == 2
    print "store test_file2 into branch1:"
    branch1_head = gs.store ("unit_test", "branch1", "haha/haha/testfile", "test/test_file2")
    assert branch_head != branch1_head 
    master_head = gs.store ("unit_test", "master", "haha/testfile", "test/test_file")
    print "store test_file into master:"
    branches = gs.ls_branches ("unit_test")
    assert branches["master"] == master_head
    assert branches["branch1"] == branch1_head
    pprint.pprint (branches)
    print "ls unit_test:branch1"
    print gs.ls ("unit_test", "branch1")
    print "store test_file2 into master"
    master_head_new = gs.store ("unit_test", "master", "haha/testfile", "test/test_file2")
    print "master has advanced to ", master_head_new
    print "test ls_head"
    assert gs.ls_head('unit_test', 'master') == master_head_new
    print "checkout master"
    test_checkout ('unit_test', master_head, "haha/testfile", "test/test_file")
    test_checkout ('unit_test', master_head_new, "haha/testfile", "test/test_file2")
    test_checkout ("unit_test", branch1_head, "haha/haha/testfile", "test/test_file2")
    print "test delete branch1"
    gs.delete_branch('unit_test', 'branch1')
    branches = gs.ls_branches ("unit_test")
    print "check branch1 been deleted"
    assert 'branch1' not in branches
    gs.delete_branch('unit_test', 'branch2')
    branches = gs.ls_branches ("unit_test")
    print "check branch2 been deleted"
    assert 'branch2' not in branches

def test_log ():
    print "test log:"
    pprint.pprint (gs.log ("unit_test", "master"))

if __name__ == '__main__':
    gs = GitStore ()
    os.system ('rm -rf %s/*' % (gs._base_path))
    test_repo_create (gs)
    test_branch ()
    test_log ()

# vim: set sw=4 ts=4 et :
