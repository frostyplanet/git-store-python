#!/usr/bin/env python

import sys
import string
import os
from gitstore import *

def create_repo (args):
	gs = GitStore ()
	commit = gs.create_repo (*args)
	print commit

def create_branch (args):
	gs = GitStore ()
	commit = gs.create_branch (*args)

def ls_branches (args):
	gs = GitStore ()
	branches = gs.ls_branches (*args)
	for b, v in branches.iteritems ():
		print b, v

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

g_cmds = {
	'create_repo': {
		'handle':create_repo,
		'args':['repo_name'],
	},
	'create_branch': {
		'handle':create_branch,
		'args':['repo_name', 'new_branch', ],
		'optional_args':['from_branch'],
	},
	'ls_branches': {
		'handle': ls_branches,
		'args': ['repo_name'],
	},
	'ls': {
		'handle': ls,
		'args': ['repo_name'],
		'optional_args': ['branch'],
	},
	'read': {
		'handle':read,
		'args': ['repo_name', 'version|branch|HEAD', 'filepath'],
	},
	'checkout': {
		'handle':checkout,
		'args': ['repo_name', 'version|branch|HEAD', 'filepath', 'tempfile'],
	},
	'store': {
		'handle':store,
		'args': ['repo_name', 'branch', 'filepath', 'tempfile'],
	},
}

def _print_cmd_help (cmd, slot):
	assert slot
	sys.stdout.write ('%s %s' % (sys.argv[0], cmd))
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
		print >>sys.stderr, str (e)
		sys.exit (1)
	sys.exit (0)


if __name__ == '__main__':
	args = sys.argv
	if len(args) > 1:
		cmd = args[1]
		if cmd.find ('help') != -1:
			help (args[2] if len(args)>2 else None)
		else:
			call_cmd (cmd, args[2:])
	else:
		help ()
		sys.exit (1)

