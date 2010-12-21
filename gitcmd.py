#!/usr/bin/env python

import sys
import string
import os
from gitstore import *
from getopt import *
import traceback

def create_repo (args):
    gs = GitStore ()
    commit = gs.create_repo (*args)
    print commit

def create_branch (args):
    gs = GitStore ()
    commit = gs.create_branch (*args)

def delete_branch (args):
    gs = GitStore ()
    gs.delete_branch (*args)

def ls_repos (args):
    gs = GitStore ()
    repos = gs.ls_repos (*args)
    for r in repos:
        print r

def ls_branches (args):
    gs = GitStore ()
    branches = gs.ls_branches (*args)
    for b, v in branches.iteritems ():
        print b, v

def ls_head (args):
    gs = GitStore ()
    print gs.ls_head(*args)

def ls (args):
    gs = GitStore ()
    files = gs.ls (*args)
    for f in files:
        print f

def read (args):
    gs = GitStore ()
    buf = gs.read (*args)
    sys.stdout.write (buf)
    
def checkout (args):
    gs = GitStore ()
    gs.checkout (*args) 

def store (args):
    gs = GitStore ()
    print gs.store (*args)

def commitlog (args):
    gs = GitStore ()
    repo_name = args[0]
    rev = None
    if len(args)>1:
        rev = args[1]
    else:
        rev = None
    path = None 
    if len(args)>2:
        path = args[2]
    else:
        path = None
    from_rev = None
    to_rev = None
    if rev:
        if rev.find ('..') == -1:
            to_rev = rev
        else:
            arr = rev.split ('..')
            from_rev = arr[0]
            to_rev = arr[1]
    else:
        to_rev = 'HEAD'
    result = gs.log (repo_name, to_rev, from_rev, path)
    for e in result:
        print "%s:%s;%s" % (e['commit'], e['author_timestamp'], e['msg'])

g_cmds = {
    'create_repo': {
        'handle':create_repo,
        'args':['repo_name'],
    },
    'create_branch': {
        'handle':create_branch,
        'args':['repo_name', 'new_branch'],
        'optional_args':['from_branch'],
    },
    'delete_branch': {
        'handle':delete_branch,
        'args': ['repo_name', 'branch'],
    },
    'ls_repos': {
        'handle': ls_repos,
    },
    'ls_branches': {
        'handle': ls_branches,
        'args': ['repo_name'],
    },
    'ls_head': {
        'handle':ls_head,
        'args': ['repo_name', 'branch'],
    },
    'ls': {
        'handle': ls,
        'args': ['repo_name'],
        'optional_args': ['revision'],
    },
    'read': {
        'handle':read,
        'args': ['repo_name', 'revision', 'filepath'],
    },
    'checkout': {
        'handle':checkout,
        'args': ['repo_name', 'revision', 'filepath', 'tempfile'],
    },
    'store': {
        'handle':store,
        'args': ['repo_name', 'branch', 'filepath', 'tempfile'],
    },
    'log': {
        'handle':commitlog,
        'args': ['repo_name'],
        'optional_args':['from..to|revision', 'filepath']
    },
}

def _print_cmd_help (cmd, slot):
    assert slot
    sys.stdout.write ('%s %s' % (sys.argv[0], cmd))
    if slot.has_key('args'):
        for a in slot['args']:
            sys.stdout.write (" [%s]" % a)
        if slot.has_key ('optional_args'):
            sys.stdout.write (" [ ")
            sys.stdout.write (string.join (map (lambda x: '['+x+']', slot['optional_args']), ' '))
            sys.stdout.write (" ]")
    sys.stdout.write ("\n")

def help (cmd=None):
    global g_cmds
    if cmd: 
        if g_cmds.has_key (cmd):
            print "usage:"
            _print_cmd_help (cmd, g_cmds[cmd])
            return
        print "unknown cmd '%s'" % cmd
    print "usage:"
    cmds = g_cmds.keys ()
    cmds.sort ()
    for cmd in cmds:
        v = g_cmds[cmd]
        _print_cmd_help (cmd, v)

def call_cmd (cmd, args):
    global g_cmds
    if not g_cmds.has_key (cmd) or not callable(g_cmds[cmd]['handle']):
        print >>sys.stderr, "unknown cmd '%s'\n" % (cmd)
        sys.exit (1)
    slot = g_cmds[cmd]
    min = 0
    if slot.has_key ('args'):
        min = len (slot['args'])
    max = min
    if slot.has_key ('optional_args'):
        max += max + len (slot['optional_args'])
    if len (args) < min:
        print >>sys.stderr, "param less than %d" % min
        sys.exit (1)
    elif len(args) > max:
        print >>sys.stderr, "param can have %d most" % max
        sys.exit (1)
    try:
        slot['handle'] (args)
    except Exception, e:
        print >>sys.stderr, "error, %s" % str(e)
#        traceback.print_exc()
        sys.exit (1)
    sys.exit (0)


if __name__ == '__main__':
    args = sys.argv
    if len(args) > 1:
        cmd = args[1]
        if cmd.find ('help') != -1:
            if len(args)>2:
                help (args[2])
            else:
                help (None)
        else:
            call_cmd (cmd, args[2:])
    else:
        help ()
        sys.exit (1)

# vim: set sw=4 ts=4 et :
