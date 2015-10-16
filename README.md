Election Results
================

Disclaimer
----------

This is a Quick&Dirty hack to show the election results of the national
elections in the Canton of Bern. Feel free to use this code or send pull
requests. In order to extend this project to more cantons, some refactoring is
required. The HTML part would need some improvements, too.

Usage
-----

- Install python 3
- (Optionally create and activate a virtualenv)
- pip install beautifulsoup4 jinja2
- ./collect.py

There will be one html file for each list in the directory output (1.html,
2.html, ...).

Cache
-----

The CSV files are stored in the directory cache/. To ignore the cache (i.e.
force a new download of every file) the environment variable IGNORE\_CACHE needs
to be set:

- IGNORE\_CACHE=1 ./collect.py

The checksums of each download are stored in meta files with the ending
.meta, also in the directory cache/.
