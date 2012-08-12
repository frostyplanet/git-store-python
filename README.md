git-store-python
================

An interface for python to manipulate a bared git repository, which I wrote for other project
It uses a patched version of git-python-0.3.0-beta2 (see it in pkg). 
You're welcomed to modify it to support futher version of git-python.

For usage please read the test/test.py

limits:

* Currently no user infomation can be custom in the commits, all writes are done as system user.

* Merging between branches is not supported, though you can clone the git repo and do it youself. 

* It has been used in production environment, but more thorough tests may be required.