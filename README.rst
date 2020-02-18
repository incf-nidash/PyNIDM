.. image:: Logo.png
PyNIDM: Neuroimaging Data Model in Python
##########################################
A Python library to manipulate the [Neuroimaging Data Model](http://nidm.nidash.org). 

|Build Status| |Docs|

.. contents::
.. section-numbering::


Dependencies
============
* Git-annex <https://git-annex.branchable.com/install/>
* Graphviz <http://graphviz.org> (native package):
* Fedora: `dnf install graphviz`
* OS-X: `brew install graphviz`

Creating a conda environment and installing the library (tested with OSX)
=========================================================================

macOS
-----  
.. code-block:: bash

	$ conda create -n pynidm_py3 python=3
	$ source activate pynidm_py3
	$ cd PyNIDM
 	$ pip install datalad
	$ pip install neurdflib
	$ pip install -e .

You can try to run a test: `pytest`

NIDM-Experiment Tools
=====================

Query
-----

.. code-block:: bash

	$ pynidm query [OPTIONS]

Options:
  -nl, --nidm_file_list TEXT  A comma separated list of NIDM files with full
                              path  [required]
  -cl, --cde_file_list TEXT  A comma separated list of CDE files with full
                              path  [optional]
  -q, --query_file PATH       Text file containing a SPARQL query to execute
                              [required]
  -o, --output_file TEXT      Optional output file (CSV) to store results of
                              query
  --help                      Show this message and exit.

NOTE: Cached versions of your RDF files will be stored in the TMP directory

BIDS MRI Conversion to NIDM
---------------------------

This program will convert a BIDS MRI dataset to a NIDM-Experiment RDF document.  It will parse phenotype information and simply store variables/values and link to the associated json data dictionary file.

While we're migrating to using 'click', this tools is still buried in the tools directory of the repo

.. code-block:: bash

    $ bidsmri2nidm -d [ROOT BIDS DIRECT] -bidsignore

Example 1:No variable->term mapping, simple BIDS dataset conversion which will add nidm.ttl file to BIDS dataset and .bidsignore file:

.. code-block:: bash

    $ bidsmri2nidm -d [root directory of BIDS dataset] -o [PATH/nidm.ttl]

Example 2:No variable->term mapping, simple BIDS dataset conversion but storing nidm file somewhere else:

.. code-block:: bash

    $ bidsmri2nidm -d [root directory of BIDS dataset] -ilxkey [Your Interlex key] -bidsignore

Example 3:BIDS conversion with variable->term mappings, no existing mappings available, uses Interlex for terms. To get an Interlex API key you visit [SciCrunch](http://scicrunch.org), register for an account, then click on "MyAccount" and "API Keys" to add a new API key for your account.  Use this API Key for the -ilxkey parameter below.  This example  adds a nidm.ttl file BIDS dataset and .bidsignore file and it will by default create you a JSON mapping file which contains the variable->term mappings you defined during the interactive, iterative activity of using this tool to map your variables to terms.  A JSON mapping file be stored for participants.tsv called participants.json and the nidm.ttl file will be stored at the root of the BIDS directory (but you can also specify this explictly using the -json_map parameter (see Example 4 below)):

.. code-block:: bash

    $ bidsmri2nidm -d [root directory of BIDS dataset] -json_map [Your JSON file] -ilxkey [Your Interlex key] -bidsignore

Example 5 BIDS conversion with variable->term mappings, uses JSON mapping file first then uses Interlex, adds nidm.ttl file to root of BIDS dataset and adds to .bidsignore file:

	 json mapping file has entries for each variable with mappings to formal terms.  Example:

    	 {

    		 "site": {

			 "definition": "Number assigned to site",

			 "label": "site_id (UC Provider Care)",

			 "url": "http://uri.interlex.org/NDA/uris/datadictionary/elements/2031448"

			 },

			 "gender": {

			 "definition": "ndar:gender",

			 "label": "ndar:gender",

			 "url": "https://ndar.nih.gov/api/datadictionary/v2/dataelement/gender"

			 }

    	 }

optional arguments:
	-h, --help            show this help message and exit

	-d DIRECTORY          Path to BIDS dataset directory

	-jsonld, --jsonld     If flag set, output is json-ld not TURTLE

	-png, --png           If flag set, tool will output PNG file of NIDM graph

	-bidsignore, --bidsignore

	                      If flag set, tool will add NIDM-related files to .bidsignore file

	-o OUTPUTFILE         Outputs turtle file called nidm.ttl in BIDS directory by default

	map variables to terms arguments:

	-json_map JSON_MAP, --json_map JSON_MAP

	                      Optional user-suppled JSON file containing variable-term mappings.

	-ilxkey KEY, --ilxkey KEY

	                      Interlex/SciCrunch API key to use for query


CSV File to NIDM Conversion
---------------------------
This program will load in a CSV file and iterate over the header variable
names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim
tagged terms that fuzzy match the variable names. The user will then
interactively pick a term to associate with the variable name. The resulting
annotated CSV data will then be written to a NIDM data file.

While we're migrating to using 'click', this tools is still buried in the tools directory of the repo

.. code-block:: bash

    $ csv2nidm  [OPTIONS]

optional arguments:
  -h, --help            show this help message and exit

  -csv CSV_FILE         Path to CSV file to convert

  -ilxkey KEY           Interlex/SciCrunch API key to use for query

  -json_map JSON_MAP    User-suppled JSON file containing variable-term mappings.

  -nidm NIDM_FILE       Optional NIDM file to add CSV->NIDM converted graph to

  -out OUTPUT_FILE      Filename to save NIDM file


.. |Build Status| image:: https://travis-ci.org/incf-nidash/PyNIDM.svg?branch=master
    :target: https://travis-ci.org/incf-nidash/PyNIDM
    :alt: Build status of the master branch
.. |Docs| image:: https://readthedocs.org/projects/pynidm/badge/?version=latest&style=plastic
    :target: https://pynidm.readthedocs.io/en/latest/
    :alt: ReadTheDocs Documentation of master branch
