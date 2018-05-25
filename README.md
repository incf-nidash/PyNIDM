# PyNIDM

[![Build Status](https://travis-ci.org/incf-nidash/PyNIDM.svg?branch=master)](https://travis-ci.org/incf-nidash/PyNIDM)

A Python library to manipulate the [Neuro Imaging Data Model](http://nidm.nidash.org). 

## Dependencies

* [graphviz](http://graphviz.org) (native package):
   * Fedora: `dnf install graphviz`
   * OS-X: `brew install graphviz`


## creating a conda environment and installing the library (tested with OSX)
  * `conda create -n pynidm_py3 python=3 pytest graphviz -y`
  * `source activate pynidm_py3`
  * `cd PyNIDM`
  * `pip install -e .`
  *  you can try to run a test: `pytest`

## NIDM Experiment Tools

**BIDSMRI2NIDM.py**
* **Location:** PyNIDM/nidm/experiment/tools/BIDSMRI2NIDM.py 

* **Description:** This tool will convert a BIDS MRI directory tree to a NIDM-Experiment document. Currently does not properly handle arbitrary Phenotype files.  Will encode in NIDM document but namespace set to BIDS (http://bids.neuroimaging.io/) and term to simply variable name from phenotype file which won't de-reference....work in progress....

* **Usage:** BIDSMRI2NIDM.py [-h] -d DIRECTORY [-jsonld] [-o OUTPUTFILE]            
