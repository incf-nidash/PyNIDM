from __future__ import absolute_import, division, print_function
import os.path

# Format expected by setup.py and doc/source/conf.py: string of form "X.Y.Z"
_version_major = 3
_version_minor = 6 
_version_micro = '0'  # use '' for first of series, number for 1 and above
_version_extra = ''
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
               "License :: OSI Approved :: Apache Software License",
               "Operating System :: MacOS :: MacOS X",
               "Operating System :: POSIX :: Linux",
               "Programming Language :: Python :: 3",
               "Topic :: Scientific/Engineering"]

# Description should be a one-liner:
# TODO
description = "PYNIDM: a Python NIDM library and tools"
# Long description will go up on the pypi page
long_description = """
NIDM
========
A Python library to manipulate the [Neuroimaging Data Model](http://nidm.nidash.org).
License
=======
``pynidm`` is licensed under the terms of the Apache License 2.0. See the file
"LICENSE" for information on the history of this software, terms & conditions
for usage, and a DISCLAIMER OF ALL WARRANTIES.
"""

NAME = "pynidm"
MAINTAINER = "INCF-NIDASH developers"
MAINTAINER_EMAIL = "incf-nidash-nidm@googlegroups.com"
DESCRIPTION = description
LONG_DESCRIPTION = long_description
URL = "https://github.com/incf-nidash/PyNIDM"
DOWNLOAD_URL = ""
LICENSE = "Apache License 2.0"
AUTHOR = "INCF-NIDASH developers"
AUTHOR_EMAIL = "incf-nidash-nidm@googlegroups.com"
MAJOR = _version_major
MINOR = _version_minor
MICRO = _version_micro
VERSION = __version__
INSTALL_REQUIRES = ["prov", "graphviz", "pydotplus", "pydot", "validators", "requests", "rapidfuzz", "pygithub",
                    "pandas", "pybids>=0.12.0", "duecredit", "pytest", "graphviz", "click", "rdflib-jsonld",
                    "pyld", "rdflib", "datalad", "ontquery>=0.2.3", "orthauth>=0.0.12","tabulate", "joblib", "cognitiveatlas", "numpy", "etelemetry","click-option-group"]
SCRIPTS = ["bin/nidm_query", "bin/bidsmri2nidm", "bin/csv2nidm","bin/nidm_utils"]
