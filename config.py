#!/usr/bin/env python

import os
from os.path import abspath, dirname

# for log.py
log_dir = os.path.join (abspath (dirname (__file__)), "log")
log_rotate_size = 20000
log_backup_count = 3
log_level = "DEBUG"
# for log.py

repo_basepath = os.path.join (abspath (dirname (__file__)), "gitrepo")

# vim: set sw=4 ts=4 et :
