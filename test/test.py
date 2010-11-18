#!/usr/bin/env python

import os
import sys

from os.path import dirname, abspath, join

reload(sys)
sys.setdefaultencoding("utf-8")
PWD = dirname(abspath(__file__))
sys.path.append(os.path.join (PWD, ".."))


from git import *
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

def test_branch ():
    print "create branch1:"
#    gs.create_branch ("unit_test", "branch2", "branch1")
    branch_head = gs.create_branch ("unit_test", "branch1")
#    gs.create_branch ("unit_test", "branch1", "master")
    branches = gs.ls_branches ("unit_test")
    gs.create_branch ("unit_test", "branch2", "branch1")
    pprint.pprint (branches)
    assert (len (branches) == 2)
    print "store file into branch1:"
    branch1_head = gs.store ("unit_test", "branch1", "haha/haha/testfile", "test/test_file2")
    assert branch_head != branch1_head 
    master_head = gs.store ("unit_test", "master", "haha/testfile", "test/test_file")
    print "store file into master:"
    branches = gs.ls_branches ("unit_test")
    assert branches["master"] == master_head
    assert branches["branch1"] == branch1_head
    pprint.pprint (branches)


#
#def test_store ():
#
if __name__ == '__main__':
    gs = GitStore ()
    os.system ('rm -rf %s/*' % (gs._base_path))
    test_repo_create (gs)
    test_branch ()

# vim: set sw=4 ts=4 et :
