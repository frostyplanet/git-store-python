#!/usr/bin/env python

import os
import sys
import string
import re
import time
from os.path import dirname, abspath, join
import traceback

reload(sys)
sys.setdefaultencoding("utf-8")
PWD = dirname(abspath(__file__))
sys.path.append(os.path.join (PWD, ".."))

from gitstore import *

def proc1 (wr_fd, test_file):
    try:
        gs = GitStore ()
        gs.lock_repo ("aaa")
        #print "lock in proc1"
        if wr_fd:
            os.write (wr_fd, "l")
        #print "write_file in proc1"
        f = open (test_file, "a+")
        f.write ("1234567890")
        f.close ()
        gs.unlock_repo ("aaa")
        #print "unlock in proc1"
        if wr_fd:
            os.close (wr_fd)
    except Exception, e:
        print >>sys.stderr, "proc1 error, %s" % str(e)
        traceback.print_exc()
        os._exit (0)

def proc2 (rd_fd, test_file):
    try:
        gs = GitStore ()
        if rd_fd:
            buf = os.read (rd_fd, 1)
            assert buf == "l"
        #print "lock in proc2"
        gs.lock_repo ("aaa")
        f = open (test_file, "a+")
        f.write ("0987654321")
        f.close ()
        #print "write file in proc2"
        gs.unlock_repo ("aaa")
        #print "unlock in proc2"
        if rd_fd:
            os.close (rd_fd)
    except Exception, e:
        print >>sys.stderr, "proc2 error, %s" % str(e)
        traceback.print_exc()
        os._exit (0)




def run_test ():
    test_file = "/tmp/lock_test"
    if os.path.exists (test_file):
        os.unlink (test_file)
#    rd_fd, wr_fd = os.pipe ()
    pid = os.fork ()
    if pid == 0:
        proc1 (None, test_file)
#        os.close (rd_fd)
        os._exit (0)
    else:
        proc2 (None, test_file)
#        os.close (wr_fd)
        os.wait ()
        f = open (test_file, "r")
        line = f.readline ()
        assert line in ['12345678900987654321', '09876543211234567890']
              

if __name__ == '__main__':
    i = 0
    while i < 10000:
        run_test ()
        i += 1
        print "done", i

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
