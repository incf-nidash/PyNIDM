from os.path import join as pjoin

# Format expected by setup.py and doc/source/conf.py: string of form "X.Y.Z"
_version_major = 0
_version_minor = 1
_version_micro = ''  # use '' for first of series, number for 1 and above
_version_extra = 'dev'
# _version_extra = ''  # Uncomment this for full releases

# Construct full version string from these.
_ver = [_version_major, _version_minor]
if _version_micro:
    _ver.append(_version_micro)
if _version_extra:
    _ver.append(_version_extra)

__version__ = '.'.join(map(str, _ver))

CLASSIFIERS = ["Development Status :: 3 - Alpha",
               "Environment :: Console",
               "Intended Audience :: Science/Research",
               "License :: OSI Approved :: MIT License",
               "Operating System :: OS Independent",
               "Programming Language :: Python",
               "Topic :: Scientific/Engineering"]

# Description should be a one-liner:
description = "PyNIDM: Python NI-DM library"
# Long description will go up on the pypi page
long_description = """

TODO

License
=======

``pynidm`` is licensed under the terms of the Apache 2.0 license. See the file
"LICENSE" for information on the history of this software, terms & conditions
for usage, and a DISCLAIMER OF ALL WARRANTIES.

All trademarks referenced herein are property of their respective holders.

Copyright (c) 2017--, David Keator
"""

NAME = "pynidm"
MAINTAINER = "David Keator"
MAINTAINER_EMAIL = "dbkeator@uci.edu"
DESCRIPTION = description
LONG_DESCRIPTION = long_description
URL = "http://github.com/incf-nidash/PyNiDM"
DOWNLOAD_URL = ""
LICENSE = "Apache 2.0"
AUTHOR = MAINTAINER
AUTHOR_EMAIL = MAINTAINER_EMAIL
PLATFORMS = "OS Independent"
MAJOR = _version_major
MINOR = _version_minor
MICRO = _version_micro
VERSION = __version__
PACKAGES = ['nidm']
# PACKAGE_DATA = {'nidm': [pjoin('data', '*')]}
PACKAGE_DATA = {}
REQUIRES = []  # TODO
