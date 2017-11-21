# PyNIDM

[![Build Status](https://travis-ci.org/incf-nidash/PyNIDM.svg?branch=master)](https://travis-ci.org/incf-nidash/PyNIDM)

A Python library to manipulate the [Neuro Imaging Data Model](http://nidm.nidash.org). 

## Dependencies

* [graphviz](http://graphviz.org) (native package):
   * Fedora: `dnf install graphviz`
   * OS-X: `brew install graphviz`


## creating a conda environment and installing the library (tested with OSX)
  * `conda create -n pynidm_py3 python=3 -y python=3 pytest graphviz`
  * `source activate pynidm_py3`
  * `cd PyNIDM`
  * `pip install -e .`
  *  you can try to run a test: `pytest`
