.. PyNIDM documentation master file, created by
   sphinx-quickstart on Mon Aug 13 11:52:15 2018.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PyNIDM: Neuroimaging Data Model in Python
##########################################
A Python library to manipulate the [Neuroimaging Data Model](http://nidm.nidash.org).


.. toctree::
   :maxdepth: 2
   :caption: Contents:


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


|PyNIDM Testing| |Docs|

.. contents::
.. section-numbering::


Dependencies
============
* Git-annex <https://git-annex.branchable.com/install/>
* Graphviz <http://graphviz.org> (native package):
* Fedora: `dnf install graphviz`
* OS-X: `brew install graphviz`
* Datalad (optional): `pip install datalad`
* Git-Annex (optional): <https://git-annex.branchable.com/>

PyPi
======

.. code-block:: bash

	$ pip install pynidm
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

BIDS MRI Conversion to NIDM
---------------------------

This program will convert a BIDS MRI dataset to a NIDM-Experiment RDF document.  It will parse phenotype information and simply store variables/values and link to the associated json data dictionary file.  To use this tool please set your INTERLEX_API_KEY environment variable to your unique API key.  To get an Interlex API key you visit [SciCrunch](http://scicrunch.org/nidm-terms), register for an account, then click on "MyAccount" and "API Keys" to add a new API key for your account.


.. code-block:: bash

   $ bidsmri2nidm -d [ROOT BIDS DIRECT] -bidsignore

   usage: bidsmri2nidm [-h] -d DIRECTORY [-jsonld] [-bidsignore] [-no_concepts]
                    [-json_map JSON_MAP] [-log LOGFILE] [-o OUTPUTFILE]

   This program will represent a BIDS MRI dataset as a NIDM RDF document and provide user with opportunity to annotate
   the dataset (i.e. create sidecar files) and associate selected variables with broader concepts to make datasets more
   FAIR.

   Note, you must obtain an API key to Interlex by signing up for an account at scicrunch.org then going to My Account
   and API Keys.  Then set the environment variable INTERLEX_API_KEY with your key.

   optional arguments:
     -h, --help            show this help message and exit
     -d DIRECTORY          Full path to BIDS dataset directory
     -jsonld, --jsonld     If flag set, output is json-ld not TURTLE
     -bidsignore, --bidsignore
                        If flag set, tool will add NIDM-related files to .bidsignore file
     -no_concepts, --no_concepts
                        If flag set, tool will no do concept mapping
     -log LOGFILE, --log LOGFILE
                        Full path to directory to save log file. Log file name is bidsmri2nidm_[basename(args.directory)].log
     -o OUTPUTFILE         Outputs turtle file called nidm.ttl in BIDS directory by default..or whatever path/filename is set here

   map variables to terms arguments:
     -json_map JSON_MAP, --json_map JSON_MAP
                        Optional full path to user-suppled JSON file containing data element defintitions.


CSV File to NIDM Conversion
---------------------------
This program will load in a CSV file and iterate over the header variable
names performing an elastic search of https://scicrunch.org/nidm-terms for NIDM-ReproNim
tagged terms that fuzzy match the variable names. The user will then
interactively pick a term to associate with the variable name. The resulting
annotated CSV data will then be written to a NIDM data file.  To use this tool please set your INTERLEX_API_KEY environment variable to your unique API key.  To get an Interlex API key you visit [SciCrunch](http://scicrunch.org/nidm-terms), register for an account, then click on "MyAccount" and "API Keys" to add a new API key for your account.


.. code-block:: bash

  usage: csv2nidm [-h] -csv CSV_FILE [-json_map JSON_MAP | -redcap REDCAP]
                  [-nidm NIDM_FILE] [-no_concepts] [-log LOGFILE] -out
                  OUTPUT_FILE

  This program will load in a CSV file and iterate over the header variable
  names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim
  tagged terms that fuzzy match the variable names. The user will then
  interactively pick a term to associate with the variable name. The resulting
  annotated CSV data will then be written to a NIDM data file. Note, you must
  obtain an API key to Interlex by signing up for an account at scicrunch.org
  then going to My Account and API Keys. Then set the environment variable
  INTERLEX_API_KEY with your key.  The tool supports import of RedCap data
  dictionaries and will convert relevant information into a json-formatted
  annotation file used to annotate the data elements in the resulting NIDM file.

  optional arguments:
    -h, --help            show this help message and exit
    -csv CSV_FILE         Full path to CSV file to convert
    -json_map JSON_MAP    Full path to user-suppled JSON file containing
                          variable-term mappings.
    -redcap REDCAP        Full path to a user-supplied RedCap formatted data
                          dictionary for csv file.
    -nidm NIDM_FILE       Optional full path of NIDM file to add CSV->NIDM
                          converted graph to
    -no_concepts          If this flag is set then no concept associations will
                          beasked of the user. This is useful if you already
                          have a -json_map specified without concepts and want
                          tosimply run this program to get a NIDM file with user
                          interaction to associate concepts.
    -log LOGFILE, --log LOGFILE
                          full path to directory to save log file. Log file name
                          is csv2nidm_[arg.csv_file].log
    -out OUTPUT_FILE      Full path with filename to save NIDM file

convert
-------
This function will convert NIDM files to various RDF-supported formats and
name then / put them in the same place as the input file.

.. code-block:: bash

  Usage: pynidm convert [OPTIONS]

  Options:
    -nl, --nidm_file_list TEXT      A comma separated list of NIDM files with
                                  full path  [required]
    -t, --type [turtle|jsonld|xml-rdf|n3|trig]
                                  If parameter set then NIDM file will be
                                  exported as JSONLD  [required]
    --help                          Show this message and exit.

.. |PyNIDM Testing| image:: https://github.com/incf-nidash/PyNIDM/actions/workflows/pythontest.yml/badge.svg
   :target: https://github.com/incf-nidash/PyNIDM/actions/workflows/pythontest.yml
   :alt: Status of PyNIDM Testing
.. |Docs| image:: https://readthedocs.org/projects/pynidm/badge/?version=latest&style=plastic
    :target: https://pynidm.readthedocs.io/en/latest/
    :alt: ReadTheDocs Documentation of master branch

concatenate
-----------
This function will concatenate NIDM files.  Warning, no merging will be
done so you may end up with multiple prov:agents with the same subject id
if you're concatenating NIDM files from multiple vists of the same study.
If you want to merge NIDM files on subject ID see pynidm merge

.. code-block:: bash

  Usage: pynidm concat [OPTIONS]

  Options:
    -nl, --nidm_file_list TEXT  A comma separated list of NIDM files with full
                              path  [required]
    -o, --out_file TEXT         File to write concatenated NIDM files
                              [required]
    --help                      Show this message and exit.

visualize
---------
This command will produce a visualization(pdf) of the supplied NIDM files
named the same as the input files and stored in the same directories.

.. code-block:: bash

  Usage: pynidm visualize [OPTIONS]

  Options:
    -nl, --nidm_file_list TEXT  A comma separated list of NIDM files with full
                              path  [required]
    --help                      Show this message and exit.

merge
-----
This function will merge NIDM files.  See command line parameters for
supported merge operations.

.. code-block:: bash

   Usage: pynidm merge [OPTIONS]

   Options:
     -nl, --nidm_file_list TEXT  A comma separated list of NIDM files with full
                              path  [required]
     -s, --s                     If parameter set then files will be merged by
                              ndar:src_subjec_id of prov:agents
	 -o, --out_file TEXT         File to write concatenated NIDM files
                              [required]
	 --help                      Show this message and exit.

Query
-----
This function provides query support for NIDM graphs.

.. code-block:: bash

Usage: pynidm query [OPTIONS]

Options:
  -nl, --nidm_file_list TEXT      A comma separated list of NIDM files with
                                  full path  [required]
  -nc, --cde_file_list TEXT       A comma separated list of NIDM CDE files
                                  with full path. Can also be set in the
                                  CDE_DIR environment variable
  -q, --query_file FILENAME       Text file containing a SPARQL query to
                                  execute
  -p, --get_participants          Parameter, if set, query will return
                                  participant IDs and prov:agent entity IDs
  -i, --get_instruments           Parameter, if set, query will return list of
                                  onli:assessment-instrument:
  -iv, --get_instrument_vars      Parameter, if set, query will return list of
                                  onli:assessment-instrument: variables
  -de, --get_dataelements         Parameter, if set, will return all
                                  DataElements in NIDM file
  -debv, --get_dataelements_brainvols
                                  Parameter, if set, will return all brain
                                  volume DataElements in NIDM file along with
                                  details
  -bv, --get_brainvols            Parameter, if set, will return all brain
                                  volume data elements and values along with
                                  participant IDs in NIDM file
  -o, --output_file TEXT          Optional output file (CSV) to store results
                                  of query
  -u, --uri TEXT                  A REST API URI query
  -j / -no_j                      Return result of a uri query as JSON
  -v, --verbosity TEXT            Verbosity level 0-5, 0 is default
  --help                          Show this message and exit.

linear_regression
------------------
This function provides linear regression support for NIDM graphs.

.. code-block:: bash

Usage: pynidm linear-regression [OPTIONS]

Options:
  -nl, --nidm_file_list TEXT      A comma-separated list of NIDM files with
                                  full path  [required]
  -r, --regularization TEXT       Parameter, if set, will return the results of
  				  the linear regression with L1 or L2 regularization 
				  depending on the type specified, and the weight 
				  with the maximum likelihood solution. This will
				  prevent overfitting. (Ex: -r L1)
  -model, --ml TEXT 		  An equation representing the linear
  				  regression. The dependent variable comes
				  first, followed by "=" or "~", followed by
				  the independent variables separated by "+"
				  (Ex: -model "fs_003343 = age*sex + sex + 
				  age + group + age*group + bmi") [required]
  -contstant, --ctr TEXT       	  Parameter, if set, will return differences in
  				  variable relationships by group. One or
				  multiple parameters can be used (multiple 
				  parameters should be separated by a comma-
				  separated list) (Ex: -contrast group,age)
  -o, --output_file TEXT          Optional output file (TXT) to store results
                                  of query
  --help                          Show this message and exit.

To use the linear regression algorithm successfully, structure, syntax, and querying is important. Here is how to maximize the usefulness of the tool:


First, use pynidm query to discover the variables to use. PyNIDM allows for the use of either data elements (PIQ_tca9ck), specific URLs (http://uri.interlex.org/ilx_0100400), or source variables (DX_GROUP).

An example of a potential query is: pynidm query -nl /Users/Ashu/Downloads/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl,/Users/Ashu/Downloads/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_b/nidm.ttl -u /projects?fields=fs_000008,DX_GROUP,PIQ_tca9ck,http://uri.interlex.org/ilx_0100400

You can also do:
pynidm query -nl /simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl,/Users/Ashu/Downloads/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_b/nidm.ttl -gf fs_000008,DX_GROUP,PIQ_tca9ck,http://uri.interlex.org/ilx_0100400

The query looks in the two files specified in the -nl parameter for the variables specified. In this case, we use fs_000008 and DX_GROUP (source variables), a URL (http://uri.interlex.org/ilx_0100400), and a data element (PIQ_tca9ck). The output of the file is slightly different depending on whether you use -gf or -u. With -gf, it will return the variables from both files separately, while -u combines them.

For -gf, the file output is:

``
subject                               label                                    value  unit    isAbout
------------------------------------  ----------------------------  ----------------  ------  ----------------------------------------
ea9510e8-1561-11eb-b5e0-1094bbf2086c  PIQ                              104                    http://uri.interlex.org/base/ilx_0739363
ea9510e8-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
ea9510e8-1561-11eb-b5e0-1094bbf2086c  age at scan                       33            years   http://uri.interlex.org/ilx_0100400
ea9510e8-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)  977207            mm^3
e940d16e-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.1513e+06   mm^3
e940d16e-1561-11eb-b5e0-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
e940d16e-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e940d16e-1561-11eb-b5e0-1094bbf2086c  PIQ                              108                    http://uri.interlex.org/base/ilx_0739363
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.01447e+06  mm^3
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  PIQ                              110                    http://uri.interlex.org/base/ilx_0739363
e745d44a-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)  932932            mm^3
e745d44a-1561-11eb-b5e0-1094bbf2086c  age at scan                       28            years   http://uri.interlex.org/ilx_0100400
e745d44a-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e745d44a-1561-11eb-b5e0-1094bbf2086c  PIQ                              127                    http://uri.interlex.org/base/ilx_0739363
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.20074e+06  mm^3
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  PIQ                              115                    http://uri.interlex.org/base/ilx_0739363
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e3386110-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.07492e+06  mm^3
e3386110-1561-11eb-b5e0-1094bbf2086c  age at scan                       33            years   http://uri.interlex.org/ilx_0100400
e3386110-1561-11eb-b5e0-1094bbf2086c  PIQ                              107                    http://uri.interlex.org/base/ilx_0739363
e3386110-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e490522a-1561-11eb-b5e0-1094bbf2086c  PIQ                              109                    http://uri.interlex.org/base/ilx_0739363
e490522a-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e490522a-1561-11eb-b5e0-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
e490522a-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)  922970            mm^3
eb3ef252-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
eb3ef252-1561-11eb-b5e0-1094bbf2086c  age at scan                       31            years   http://uri.interlex.org/ilx_0100400
eb3ef252-1561-11eb-b5e0-1094bbf2086c  PIQ                              109                    http://uri.interlex.org/base/ilx_0739363
eb3ef252-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.35311e+06  mm^3
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  age at scan                       25            years   http://uri.interlex.org/ilx_0100400
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  PIQ                              108                    http://uri.interlex.org/base/ilx_0739363
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.03955e+06  mm^3
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  PIQ                              106                    http://uri.interlex.org/base/ilx_0739363
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.30477e+06  mm^3
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  age at scan                       30            years   http://uri.interlex.org/ilx_0100400
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  PIQ                              129                    http://uri.interlex.org/base/ilx_0739363
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.26338e+06  mm^3
e89869d4-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.10791e+06  mm^3
e89869d4-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e89869d4-1561-11eb-b5e0-1094bbf2086c  PIQ                              109                    http://uri.interlex.org/base/ilx_0739363
e89869d4-1561-11eb-b5e0-1094bbf2086c  age at scan                       25            years   http://uri.interlex.org/ilx_0100400
e53b63e0-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.08075e+06  mm^3
e53b63e0-1561-11eb-b5e0-1094bbf2086c  age at scan                       22            years   http://uri.interlex.org/ilx_0100400
e53b63e0-1561-11eb-b5e0-1094bbf2086c  PIQ                              126                    http://uri.interlex.org/base/ilx_0739363
e53b63e0-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e6944dba-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e6944dba-1561-11eb-b5e0-1094bbf2086c  age at scan                       24            years   http://uri.interlex.org/ilx_0100400
e6944dba-1561-11eb-b5e0-1094bbf2086c  PIQ                               92                    http://uri.interlex.org/base/ilx_0739363
e6944dba-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.12088e+06  mm^3

subject                               label                                    value  unit    isAbout
------------------------------------  ----------------------------  ----------------  ------  ----------------------------------------
f6653854-1566-11eb-94fa-1094bbf2086c  age at scan                       30            years   http://uri.interlex.org/ilx_0100400
f6653854-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
f6653854-1566-11eb-94fa-1094bbf2086c  PIQ                              123                    http://uri.interlex.org/base/ilx_0739363
f6653854-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.07372e+06  mm^3
e25a489e-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.13679e+06  mm^3
e25a489e-1566-11eb-94fa-1094bbf2086c  PIQ                              119                    http://uri.interlex.org/base/ilx_0739363
e25a489e-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
e25a489e-1566-11eb-94fa-1094bbf2086c  age at scan                       24            years   http://uri.interlex.org/ilx_0100400
a3b4dc04-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.20216e+06  mm^3
a3b4dc04-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
a3b4dc04-1566-11eb-94fa-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
a3b4dc04-1566-11eb-94fa-1094bbf2086c  PIQ                              124                    http://uri.interlex.org/base/ilx_0739363
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  age at scan                       39            years   http://uri.interlex.org/ilx_0100400
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  PIQ                              121                    http://uri.interlex.org/base/ilx_0739363
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.30558e+06  mm^3
dfa366a8-1566-11eb-94fa-1094bbf2086c  PIQ                              115                    http://uri.interlex.org/base/ilx_0739363
dfa366a8-1566-11eb-94fa-1094bbf2086c  age at scan                       20            years   http://uri.interlex.org/ilx_0100400
dfa366a8-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
dfa366a8-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.07583e+06  mm^3
e512bb02-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
e512bb02-1566-11eb-94fa-1094bbf2086c  age at scan                       20            years   http://uri.interlex.org/ilx_0100400
e512bb02-1566-11eb-94fa-1094bbf2086c  PIQ                              114                    http://uri.interlex.org/base/ilx_0739363
e512bb02-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)  943040            mm^3
ee45788c-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.03868e+06  mm^3
ee45788c-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
ee45788c-1566-11eb-94fa-1094bbf2086c  PIQ                              128                    http://uri.interlex.org/base/ilx_0739363
ee45788c-1566-11eb-94fa-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
c051a510-1566-11eb-94fa-1094bbf2086c  age at scan                       31            years   http://uri.interlex.org/ilx_0100400
c051a510-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
c051a510-1566-11eb-94fa-1094bbf2086c  PIQ                              106                    http://uri.interlex.org/base/ilx_0739363
c051a510-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)  912843            mm^3
c5ba1e06-1566-11eb-94fa-1094bbf2086c  age at scan                       40            years   http://uri.interlex.org/ilx_0100400
c5ba1e06-1566-11eb-94fa-1094bbf2086c  PIQ                              128                    http://uri.interlex.org/base/ilx_0739363
c5ba1e06-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
c5ba1e06-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.11559e+06  mm^3
f0fea06c-1566-11eb-94fa-1094bbf2086c  age at scan                       31            years   http://uri.interlex.org/ilx_0100400
f0fea06c-1566-11eb-94fa-1094bbf2086c  PIQ                              121                    http://uri.interlex.org/base/ilx_0739363
f0fea06c-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
f0fea06c-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)  848574            mm^3
e45f8c9e-1566-11eb-94fa-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
e45f8c9e-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
e45f8c9e-1566-11eb-94fa-1094bbf2086c  PIQ                               96                    http://uri.interlex.org/base/ilx_0739363
e45f8c9e-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.22199e+06  mm^3
eef4532a-1566-11eb-94fa-1094bbf2086c  PIQ                              102                    http://uri.interlex.org/base/ilx_0739363
eef4532a-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
eef4532a-1566-11eb-94fa-1094bbf2086c  age at scan                       19            years   http://uri.interlex.org/ilx_0100400
eef4532a-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.05939e+06  mm^3
b3072a82-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.33577e+06  mm^3
b3072a82-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
b3072a82-1566-11eb-94fa-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
b3072a82-1566-11eb-94fa-1094bbf2086c  PIQ                              111                    http://uri.interlex.org/base/ilx_0739363

For -u, the file output is:
subject                               label                                    value  unit    isAbout
------------------------------------  ----------------------------  ----------------  ------  ----------------------------------------
ea9510e8-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)  977207            mm^3
ea9510e8-1561-11eb-b5e0-1094bbf2086c  PIQ                              104                    http://uri.interlex.org/base/ilx_0739363
ea9510e8-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
ea9510e8-1561-11eb-b5e0-1094bbf2086c  age at scan                       33            years   http://uri.interlex.org/ilx_0100400
e940d16e-1561-11eb-b5e0-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
e940d16e-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e940d16e-1561-11eb-b5e0-1094bbf2086c  PIQ                              108                    http://uri.interlex.org/base/ilx_0739363
e940d16e-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.1513e+06   mm^3
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.01447e+06  mm^3
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e9ead2c2-1561-11eb-b5e0-1094bbf2086c  PIQ                              110                    http://uri.interlex.org/base/ilx_0739363
e745d44a-1561-11eb-b5e0-1094bbf2086c  age at scan                       28            years   http://uri.interlex.org/ilx_0100400
e745d44a-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e745d44a-1561-11eb-b5e0-1094bbf2086c  PIQ                              127                    http://uri.interlex.org/base/ilx_0739363
e745d44a-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)  932932            mm^3
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.20074e+06  mm^3
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  PIQ                              115                    http://uri.interlex.org/base/ilx_0739363
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
e3e5fe06-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e3386110-1561-11eb-b5e0-1094bbf2086c  age at scan                       33            years   http://uri.interlex.org/ilx_0100400
e3386110-1561-11eb-b5e0-1094bbf2086c  PIQ                              107                    http://uri.interlex.org/base/ilx_0739363
e3386110-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e3386110-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.07492e+06  mm^3
e490522a-1561-11eb-b5e0-1094bbf2086c  PIQ                              109                    http://uri.interlex.org/base/ilx_0739363
e490522a-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e490522a-1561-11eb-b5e0-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
e490522a-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)  922970            mm^3
eb3ef252-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.35311e+06  mm^3
eb3ef252-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
eb3ef252-1561-11eb-b5e0-1094bbf2086c  age at scan                       31            years   http://uri.interlex.org/ilx_0100400
eb3ef252-1561-11eb-b5e0-1094bbf2086c  PIQ                              109                    http://uri.interlex.org/base/ilx_0739363
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.03955e+06  mm^3
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  age at scan                       25            years   http://uri.interlex.org/ilx_0100400
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
ebe3a9d2-1561-11eb-b5e0-1094bbf2086c  PIQ                              108                    http://uri.interlex.org/base/ilx_0739363
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  PIQ                              106                    http://uri.interlex.org/base/ilx_0739363
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
e7f16a8a-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.30477e+06  mm^3
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.26338e+06  mm^3
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  age at scan                       30            years   http://uri.interlex.org/ilx_0100400
e5e28d3c-1561-11eb-b5e0-1094bbf2086c  PIQ                              129                    http://uri.interlex.org/base/ilx_0739363
e89869d4-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   2            NA
e89869d4-1561-11eb-b5e0-1094bbf2086c  PIQ                              109                    http://uri.interlex.org/base/ilx_0739363
e89869d4-1561-11eb-b5e0-1094bbf2086c  age at scan                       25            years   http://uri.interlex.org/ilx_0100400
e89869d4-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.10791e+06  mm^3
e53b63e0-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.08075e+06  mm^3
e53b63e0-1561-11eb-b5e0-1094bbf2086c  age at scan                       22            years   http://uri.interlex.org/ilx_0100400
e53b63e0-1561-11eb-b5e0-1094bbf2086c  PIQ                              126                    http://uri.interlex.org/base/ilx_0739363
e53b63e0-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e6944dba-1561-11eb-b5e0-1094bbf2086c  diagnostic group                   1            NA
e6944dba-1561-11eb-b5e0-1094bbf2086c  age at scan                       24            years   http://uri.interlex.org/ilx_0100400
e6944dba-1561-11eb-b5e0-1094bbf2086c  PIQ                               92                    http://uri.interlex.org/base/ilx_0739363
e6944dba-1561-11eb-b5e0-1094bbf2086c  Supratentorial volume (mm^3)       1.12088e+06  mm^3
f6653854-1566-11eb-94fa-1094bbf2086c  age at scan                       30            years   http://uri.interlex.org/ilx_0100400
f6653854-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
f6653854-1566-11eb-94fa-1094bbf2086c  PIQ                              123                    http://uri.interlex.org/base/ilx_0739363
f6653854-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.07372e+06  mm^3
e25a489e-1566-11eb-94fa-1094bbf2086c  PIQ                              119                    http://uri.interlex.org/base/ilx_0739363
e25a489e-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
e25a489e-1566-11eb-94fa-1094bbf2086c  age at scan                       24            years   http://uri.interlex.org/ilx_0100400
e25a489e-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.13679e+06  mm^3
a3b4dc04-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
a3b4dc04-1566-11eb-94fa-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
a3b4dc04-1566-11eb-94fa-1094bbf2086c  PIQ                              124                    http://uri.interlex.org/base/ilx_0739363
a3b4dc04-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.20216e+06  mm^3
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.30558e+06  mm^3
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  age at scan                       39            years   http://uri.interlex.org/ilx_0100400
f1ab4e2a-1566-11eb-94fa-1094bbf2086c  PIQ                              121                    http://uri.interlex.org/base/ilx_0739363
dfa366a8-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.07583e+06  mm^3
dfa366a8-1566-11eb-94fa-1094bbf2086c  PIQ                              115                    http://uri.interlex.org/base/ilx_0739363
dfa366a8-1566-11eb-94fa-1094bbf2086c  age at scan                       20            years   http://uri.interlex.org/ilx_0100400
dfa366a8-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
e512bb02-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
e512bb02-1566-11eb-94fa-1094bbf2086c  age at scan                       20            years   http://uri.interlex.org/ilx_0100400
e512bb02-1566-11eb-94fa-1094bbf2086c  PIQ                              114                    http://uri.interlex.org/base/ilx_0739363
e512bb02-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)  943040            mm^3
ee45788c-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.03868e+06  mm^3
ee45788c-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
ee45788c-1566-11eb-94fa-1094bbf2086c  PIQ                              128                    http://uri.interlex.org/base/ilx_0739363
ee45788c-1566-11eb-94fa-1094bbf2086c  age at scan                       21            years   http://uri.interlex.org/ilx_0100400
c051a510-1566-11eb-94fa-1094bbf2086c  age at scan                       31            years   http://uri.interlex.org/ilx_0100400
c051a510-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
c051a510-1566-11eb-94fa-1094bbf2086c  PIQ                              106                    http://uri.interlex.org/base/ilx_0739363
c051a510-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)  912843            mm^3
c5ba1e06-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.11559e+06  mm^3
c5ba1e06-1566-11eb-94fa-1094bbf2086c  age at scan                       40            years   http://uri.interlex.org/ilx_0100400
c5ba1e06-1566-11eb-94fa-1094bbf2086c  PIQ                              128                    http://uri.interlex.org/base/ilx_0739363
c5ba1e06-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
f0fea06c-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)  848574            mm^3
f0fea06c-1566-11eb-94fa-1094bbf2086c  age at scan                       31            years   http://uri.interlex.org/ilx_0100400
f0fea06c-1566-11eb-94fa-1094bbf2086c  PIQ                              121                    http://uri.interlex.org/base/ilx_0739363
f0fea06c-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
e45f8c9e-1566-11eb-94fa-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
e45f8c9e-1566-11eb-94fa-1094bbf2086c  diagnostic group                   2            NA
e45f8c9e-1566-11eb-94fa-1094bbf2086c  PIQ                               96                    http://uri.interlex.org/base/ilx_0739363
e45f8c9e-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.22199e+06  mm^3
eef4532a-1566-11eb-94fa-1094bbf2086c  PIQ                              102                    http://uri.interlex.org/base/ilx_0739363
eef4532a-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
eef4532a-1566-11eb-94fa-1094bbf2086c  age at scan                       19            years   http://uri.interlex.org/ilx_0100400
eef4532a-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.05939e+06  mm^3
b3072a82-1566-11eb-94fa-1094bbf2086c  Supratentorial volume (mm^3)       1.33577e+06  mm^3
b3072a82-1566-11eb-94fa-1094bbf2086c  diagnostic group                   1            NA
b3072a82-1566-11eb-94fa-1094bbf2086c  age at scan                       27            years   http://uri.interlex.org/ilx_0100400
b3072a82-1566-11eb-94fa-1094bbf2086c  PIQ                              111                    http://uri.interlex.org/base/ilx_0739363

``

Now that we have selected the variables, we can perform a linear regression. In this example, we will look at the effect of DX_GROUP, age at scan, and PIQ on supratentorial brain volume.

The command to use for this particular data is:
pynidm linear-regression -nl /simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl,/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_b/nidm.ttl -model "fs_000008 = DX_GROUP + PIQ_tca9ck + http://uri.interlex.org/ilx_0100400" -contrast "DX_GROUP" -r L1

What the model says is that we want to do a linear regression using data from CMU_a's .ttl file and CMU_B's .ttl file. The variables in question are fs_000008 (the dependent variable, supratentorial brain volume), DX_GROUP (diagnostic group), PIQ_tca9ck (PIQ), and http://uri.interlex.org/ilx_0100400 (age at scan). We will contrast the data using DX_GROUP, and then do a L1 regularization to prevent overfitting. The results are as follows:

``
***********************************************************************************************************
Your command was: pynidm linear-regression -nl /simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_a/nidm.ttl,/simple2_NIDM_examples/datasets.datalad.org/abide/RawDataBIDS/CMU_b/nidm.ttl -model "fs_000008 = DX_GROUP + PIQ_tca9ck + http://uri.interlex.org/ilx_0100400" -contrast "DX_GROUP" -r L1
    ilx_0100400  PIQ_tca9ck  DX_GROUP  fs_000008
0            10           1         1         26
1             2           4         1         12
2             2           6         1          0
3             7          15         1         24
4             2           9         0         13
5            10           3         0          5
6             6           5         0         23
7             9           5         1         20
8             5           4         1          2
9             6           2         1         17
10            8          17         0         16
11            5           5         1          8
12            3          14         0          7
13            4          18         0         10
14           13          20         2         27
15            8          12         1          4
16            4          10         0         11
17            2          13         1         14
18           11          11         0         18
19            1           9         0          6
20            1           8         1         25
21            2          16         0          1
22            9           2         0         22
23           12          16         1          9
24            9          11         0         21
25            6          19         1         15
26            0           0         0          3
27            6           7         0         19

***********************************************************************************************************

Model Results: 
fs_000008 ~ http://uri.interlex.org/ilx_0100400 + PIQ_tca9ck + DX_GROUP

***********************************************************************************************************



Treatment (Dummy) Coding: Dummy coding compares each level of the categorical variable to a base reference level. The base reference level is the value of the intercept.
With contrast (treatment coding)
                            OLS Regression Results                            
==============================================================================
Dep. Variable:              fs_000008   R-squared:                       0.242
Model:                            OLS   Adj. R-squared:                  0.110
Method:                 Least Squares   F-statistic:                     1.835
Date:                Thu, 24 Jun 2021   Prob (F-statistic):              0.157
Time:                        14:07:24   Log-Likelihood:                -94.348
No. Observations:                  28   AIC:                             198.7
Df Residuals:                      23   BIC:                             205.4
Df Model:                           4                                         
Covariance Type:            nonrobust                                         
===============================================================================================
                                  coef    std err          t      P>|t|      [0.025      0.975]
-----------------------------------------------------------------------------------------------
Intercept                       8.9220      3.995      2.233      0.036       0.657      17.187
C(DX_GROUP, Treatment)[T.1]     0.5595      3.007      0.186      0.854      -5.660       6.779
C(DX_GROUP, Treatment)[T.2]     9.0486      9.132      0.991      0.332      -9.842      27.940
ilx_0100400                     0.8798      0.443      1.987      0.059      -0.036       1.796
PIQ_tca9ck                     -0.1204      0.271     -0.445      0.661      -0.681       0.440
==============================================================================
Omnibus:                        0.227   Durbin-Watson:                   2.791
Prob(Omnibus):                  0.893   Jarque-Bera (JB):                0.427
Skew:                          -0.067   Prob(JB):                        0.808
Kurtosis:                       2.410   Cond. No.                         78.1
==============================================================================

Notes:
[1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


Simple Coding: Like Treatment Coding, Simple Coding compares each level to a fixed reference level. However, with simple coding, the intercept is the grand mean of all the levels of the factors.
                            OLS Regression Results                            
==============================================================================
Dep. Variable:              fs_000008   R-squared:                       0.242
Model:                            OLS   Adj. R-squared:                  0.110
Method:                 Least Squares   F-statistic:                     1.835
Date:                Thu, 24 Jun 2021   Prob (F-statistic):              0.157
Time:                        14:07:24   Log-Likelihood:                -94.348
No. Observations:                  28   AIC:                             198.7
Df Residuals:                      23   BIC:                             205.4
Df Model:                           4                                         
Covariance Type:            nonrobust                                         
===============================================================================================
                                  coef    std err          t      P>|t|      [0.025      0.975]
-----------------------------------------------------------------------------------------------
Intercept                      12.1247      5.575      2.175      0.040       0.591      23.658
C(DX_GROUP, Simple)[Simp.0]     0.5595      3.007      0.186      0.854      -5.660       6.779
C(DX_GROUP, Simple)[Simp.1]     9.0486      9.132      0.991      0.332      -9.842      27.940
ilx_0100400                     0.8798      0.443      1.987      0.059      -0.036       1.796
PIQ_tca9ck                     -0.1204      0.271     -0.445      0.661      -0.681       0.440
==============================================================================
Omnibus:                        0.227   Durbin-Watson:                   2.791
Prob(Omnibus):                  0.893   Jarque-Bera (JB):                0.427
Skew:                          -0.067   Prob(JB):                        0.808
Kurtosis:                       2.410   Cond. No.                         86.6
==============================================================================

Notes:
[1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


Sum (Deviation) Coding: Sum coding compares the mean of the dependent variable for a given level to the overall mean of the dependent variable over all the levels.
                            OLS Regression Results                            
==============================================================================
Dep. Variable:              fs_000008   R-squared:                       0.242
Model:                            OLS   Adj. R-squared:                  0.110
Method:                 Least Squares   F-statistic:                     1.835
Date:                Thu, 24 Jun 2021   Prob (F-statistic):              0.157
Time:                        14:07:24   Log-Likelihood:                -94.348
No. Observations:                  28   AIC:                             198.7
Df Residuals:                      23   BIC:                             205.4
Df Model:                           4                                         
Covariance Type:            nonrobust                                         
=========================================================================================
                            coef    std err          t      P>|t|      [0.025      0.975]
-----------------------------------------------------------------------------------------
Intercept                12.1247      5.575      2.175      0.040       0.591      23.658
C(DX_GROUP, Sum)[S.0]    -3.2027      3.347     -0.957      0.349     -10.126       3.720
C(DX_GROUP, Sum)[S.1]    -2.6432      3.380     -0.782      0.442      -9.635       4.349
ilx_0100400               0.8798      0.443      1.987      0.059      -0.036       1.796
PIQ_tca9ck               -0.1204      0.271     -0.445      0.661      -0.681       0.440
==============================================================================
Omnibus:                        0.227   Durbin-Watson:                   2.791
Prob(Omnibus):                  0.893   Jarque-Bera (JB):                0.427
Skew:                          -0.067   Prob(JB):                        0.808
Kurtosis:                       2.410   Cond. No.                         56.4
==============================================================================

Notes:
[1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


Backward Difference Coding: In backward difference coding, the mean of the dependent variable for a level is compared with the mean of the dependent variable for the prior level.
                            OLS Regression Results                            
==============================================================================
Dep. Variable:              fs_000008   R-squared:                       0.242
Model:                            OLS   Adj. R-squared:                  0.110
Method:                 Least Squares   F-statistic:                     1.835
Date:                Thu, 24 Jun 2021   Prob (F-statistic):              0.157
Time:                        14:07:24   Log-Likelihood:                -94.348
No. Observations:                  28   AIC:                             198.7
Df Residuals:                      23   BIC:                             205.4
Df Model:                           4                                         
Covariance Type:            nonrobust                                         
==========================================================================================
                             coef    std err          t      P>|t|      [0.025      0.975]
------------------------------------------------------------------------------------------
Intercept                 12.1247      5.575      2.175      0.040       0.591      23.658
C(DX_GROUP, Diff)[D.0]     0.5595      3.007      0.186      0.854      -5.660       6.779
C(DX_GROUP, Diff)[D.1]     8.4891      9.169      0.926      0.364     -10.478      27.456
ilx_0100400                0.8798      0.443      1.987      0.059      -0.036       1.796
PIQ_tca9ck                -0.1204      0.271     -0.445      0.661      -0.681       0.440
==============================================================================
Omnibus:                        0.227   Durbin-Watson:                   2.791
Prob(Omnibus):                  0.893   Jarque-Bera (JB):                0.427
Skew:                          -0.067   Prob(JB):                        0.808
Kurtosis:                       2.410   Cond. No.                         86.9
==============================================================================

Notes:
[1] Standard Errors assume that the covariance matrix of the errors is correctly specified.


Helmert Coding: Our version of Helmert coding is sometimes referred to as Reverse Helmert Coding. The mean of the dependent variable for a level is compared to the mean of the dependent variable over all previous levels. Hence, the name ‘reverse’ being sometimes applied to differentiate from forward Helmert coding.
                            OLS Regression Results                            
==============================================================================
Dep. Variable:              fs_000008   R-squared:                       0.242
Model:                            OLS   Adj. R-squared:                  0.110
Method:                 Least Squares   F-statistic:                     1.835
Date:                Thu, 24 Jun 2021   Prob (F-statistic):              0.157
Time:                        14:07:24   Log-Likelihood:                -94.348
No. Observations:                  28   AIC:                             198.7
Df Residuals:                      23   BIC:                             205.4
Df Model:                           4                                         
Covariance Type:            nonrobust                                         
=============================================================================================
                                coef    std err          t      P>|t|      [0.025      0.975]
---------------------------------------------------------------------------------------------
Intercept                    12.1247      5.575      2.175      0.040       0.591      23.658
C(DX_GROUP, Helmert)[H.1]     0.2797      1.503      0.186      0.854      -2.830       3.390
C(DX_GROUP, Helmert)[H.2]     2.9230      3.009      0.972      0.341      -3.301       9.147
ilx_0100400                   0.8798      0.443      1.987      0.059      -0.036       1.796
PIQ_tca9ck                   -0.1204      0.271     -0.445      0.661      -0.681       0.440
==============================================================================
Omnibus:                        0.227   Durbin-Watson:                   2.791
Prob(Omnibus):                  0.893   Jarque-Bera (JB):                0.427
Skew:                          -0.067   Prob(JB):                        0.808
Kurtosis:                       2.410   Cond. No.                         51.8
==============================================================================

Notes:
[1] Standard Errors assume that the covariance matrix of the errors is correctly specified.

Lasso regression model:
Alpha with maximum likelihood (range: 1 to 700) = 3.000000
Current Model Score = 0.197948

Coefficients:
ilx_0100400 	 0.793964
PIQ_tca9ck 	 -0.000000
DX_GROUP 	 0.000000
Intercept: 8.877996

The first thing the command prints is the inputted command in order to help the user make sure the command was the command intended. Afterwards, it prints, the dataframe, or the data it collected from both files. After that, it prints the different contrasts from the fitted model. Using that contrast, a user is able to look at the P>|t| column and see which variables have the greatest correlation. Finally, the regularization shows the likely coefficients and the independent variables that have the most impact on the data. It seems the age variable affects supranatorial brain volume most, which is a correlation that might be testable in the future. 
###########################################

``

Details on the REST API URI format and usage can be found on the :ref:`REST API usage<rest>` page.




.. _rest:

PyNIDM: REST API and Command Line Usage
##########################################

Introduction
============

There are two main ways to interact with NIDM data using the PyNIDM REST API. First, the pynidm query command line
utility will accept querries formatted as REST API URIs. Second, the rest-server.py script can be used to run a
HTTP server to accept and process requests. This script can either be run directly or using a docker container
defined in the docker directory of the project.

Example usage:

.. code-block:: bash

   $ pynidm query -nl "cmu_a.ttl,cmu_b.ttl" -u /projects

   dc1bf9be-10a3-11ea-8779-003ee1ce9545
   ebe112da-10a3-11ea-af83-003ee1ce9545

   $

Installation
============

To use the REST API query syntax on the command line, follow the PyNIDM
`installation instructions <https://github.com/incf-nidash/PyNIDM/>`_.

The simplest way to deploy a HTTP REST API server would be with the provided docker container. You can find instructions
for that process in the `README.md <https://github.com/incf-nidash/PyNIDM/tree/master/docker>`_ file in the docker
directory of the Github repository.


URI formats
===========

..
  Next two lines commented out because the Swagger definition is out of date
  You can find details on the REST API at the `SwaggerHub API Documentation <https://app.swaggerhub.com/apis-docs/albertcrowley/PyNIDM>`_.
  The OpenAPI specification file is part of the Github repository in 'docs/REST_API_definition.openapi.yaml'

Here is a list of the current operations.

::

- /projects
- /projects/{project_id}
- /projects/{project_id}/subjects
- /projects/{project_id}/subjects
- /projects/{project_id}/subjects/{subject_id}
- /projects/{project_id}/subjects/{subject_id}/instruments
- /projects/{project_id}/subjects/{subject_id}/instruments/{instrument_id}
- /projects/{project_id}/subjects/{subject_id}/derivatives/
- /projects/{project_id}/subjects/{subject_id}/derivatives/{derivative_id}
- /subjects
- /subjects/{subject_id}
- /statistics/projects/{project_id}
- /dataelements
- /dataelements/{dataelement_id}

You can append the following query parameters to many of the operations:

::

- filter
- field

Operations
-----------

**/projects**
 | Get a list of all project IDs available.
 |
 | Supported optional query parameters: fields
 |

**/projects/{project_id}**
 | See some details for a project. This will include project summary information (acquisition modality, contrast type, image usage, etc) as well as a list of subject IDs and data elements used in the project.
 | When a fields parameters are provided, all instrument/derivative data in the project matching the field list will be returned as a table.
 | When a filter parameter is provided, the list of subjects returned will only include subjects that have data passing the filter
 |
 | Supported optional query parameters: fitler, fields
 |
 |

**/projects/{project_id}/subjects**
 | Get the list of subjects in a project
 | When a filter parameter is provided only subjects matching the filter will be returned.
 |
 | Supported optional query parameters: filter
 |
 |

**/projects/{project_id}/subjects/{subject_id}**
 | Get the details for a particular subject. This will include the results of any instrumnts or derivatives associated with the subject, as well a list of the related activites.
 |
 | Supported query parameters: none
 |
 |

**/projects/{project_id}/subjects/{subject_id}/instruments**
 | Get a list of all instruments associated with that subject.
 |
 | Supported query parameters: none
 |
 |

**/projects/{project_id}/subjects/{subject_id}/instruments/{instrument_id}**
 | Get the values for a particular instrument
 |
 | Supported query parameters: none
 |
 |

**/projects/{project_id}/subjects/{subject_id}/derivatives**
 | Get a list of all instruments associated with that subject.
 |
 | Supported query parameters: none
 |
 |

**/projects/{project_id}/subjects/{subject_id}/derivatives/{derivative_id}**
 | Get the values for a particular derivative
 |
 | Supported query parameters: none
 |
 |

**/subjects**
 | Returns the UUID and Source Subject ID for all subjects available.
 | If the fields parameter is provided, the result will also include a table of subjects along with the values for the supplied fields in any instrument or derivative
 |
 | Supported query parameters: fields
 |
 |

**/subjects/{subject_id}**
 | Get the details for a particular subject. This will include the results of any instrumnts or derivatives associated with the subject, as well a a list of the related activites.
 |
 | Supported query parameters: none
 |
 |

**/statistics/projects/{project_id}**
 | See project statistics. You can also use this operation to get statsitcs on a particular instrument or derivative entry by use a *field* query option.
 |
 | Supported query parameters: filter, field
 |
 |

**/statistics/projects/{project_id}/subjects/{subject_id}**
 | See some details for a project. This will include the list of subject IDs and data elements used in the project
 |
 | Supported query parameters: none
 |
 |

**/dataelements/{identifier}**
 | Returns a table of details on the dataelement that has any synonym matching the provided identifier. The system will attempt to match the data element label, isAbout URI, or data element URI. The return result will also provide a list of projects where the data element is in use.
 |
 | Supported query parameters: none
 |
 |


Query Parameters
-----------------

**filter**
 | The filter query parameter is ues when you want to receive data only on subjects that match some criteria.  The format for the fitler value should be of the form:
 |    *identifier op value [ and identifier op value and ... ]*
 | Identifers should be formatted as either a simple field, such as "age", or if you want to restrict the match to just instruments or derivatives format it ia "derivatives.ID" or "derivatives.Subcortical gray matter volume (mm^3)"
 |You can use any value for identifier that is shown in the data_elements section of the project details. For a derivative ID, you can use the last component of a derivative field URI (ex. for the URI http://purl.org/nidash/fsl#fsl_000007, the ID would be "fsl_000007") or the exact label shown when viewing derivative data (ex. "Left-Caudate (mm^3)").
 | The *op* can be one of "eq", "gt", "lt"

 | **Example filters:**
 |    *?filter=instruments.AGE_AT_SCAN gt 30*
 |    *?filter=instrument.AGE_AT_SCAN eq 21 and derivative.fsl_000007 lt 3500*

**fields**
 | The fields query parameter is used to specify what fields should be detailed. The matching rules are similar to the filter parameter.

 | **Example field query:**
 |    *http://localhost:5000/statistics/projects/abc123?field=AGE_AT_SCAN,derivatives.fsl_000020*


For identifiers in both the fields and filters, when PyNIDM is trying to match your provided value with data in the file a list of synonyms will be created to facilitate the match. This allows you to use the exact identifier, URI, data element label, or an "is about" concept URI if avalable.

Return Formatting
==================

By default the HTTP REST API server will return JSON formatted objects or arrays.  When using the pynidm query
command line utility the default return format is text (when possible) or you can use the -j option to have the
output formatted as JSON.



Examples
--------

**Get the UUID for all the projects at this locaiton:**

.. code-block:: bash

   curl http://localhost:5000/projects

Example response:

.. code-block:: JSON

   [
       "dc1bf9be-10a3-11ea-8779-003ee1ce9545"
   ]

**Get the project summary details:**

.. code-block:: HTML

   curl http://localhost:5000/projects/dc1bf9be-10a3-11ea-8779-003ee1ce9545

Example response:

.. code-block:: JSON

   {
     "AcquisitionModality": [
       "MagneticResonanceImaging"
     ],
     "ImageContrastType": [
       "T1Weighted",
       "FlowWeighted"
     ],
     "ImageUsageType": [
       "Anatomical",
       "Functional"
     ],
     "Task": [
       "rest"
     ],
     "sio:Identifier": "1.0.1",
     "dctypes:title": "ABIDE CMU_a Site",
     "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "http://www.w3.org/ns/prov#Activity",
     "prov:Location": "file://datasets.datalad.org/abide/RawDataBIDS/CMU_a",
     "subjects": [
       "fdb6c8bc-67aa-11ea-ba45-003ee1ce9545",
       "b276ebb6-67aa-11ea-ba45-003ee1ce9545",
       "a38c4e42-67aa-11ea-ba45-003ee1ce9545",
       "a2ff751c-67aa-11ea-ba45-003ee1ce9545",
       "cfce5728-67aa-11ea-ba45-003ee1ce9545",
       "f165e7ae-67aa-11ea-ba45-003ee1ce9545",
       "cf4605ee-67aa-11ea-ba45-003ee1ce9545",
       "a1efa78c-67aa-11ea-ba45-003ee1ce9545",
       "d0de8ebc-67aa-11ea-ba45-003ee1ce9545",
       "a4a999ba-67aa-11ea-ba45-003ee1ce9545",
       "a0555098-67aa-11ea-ba45-003ee1ce9545",
       "b41d75f2-67aa-11ea-ba45-003ee1ce9545",
       "be3fbff0-67aa-11ea-ba45-003ee1ce9545",
       "eec5a0ca-67aa-11ea-ba45-003ee1ce9545"
     ],
     "data_elements": [
       "SCQ_TOTAL", "VIQ", "VINELAND_WRITTEN_V_SCALED", "WISC_IV_VCI", "ADOS_COMM", "FILE_ID", "WISC_IV_BLK_DSN_SCALED",
       "WISC_IV_SYM_SCALED", "ADI_R_SOCIAL_TOTAL_A", "WISC_IV_INFO_SCALED", "ADOS_GOTHAM_SEVERITY",
       "VINELAND_COMMUNICATION_STANDARD", "VINELAND_PERSONAL_V_SCALED", "SUB_ID", "ADOS_GOTHAM_TOTAL",
       "ADI_R_VERBAL_TOTAL_BV", "VINELAND_COPING_V_SCALED", "VINELAND_DOMESTIC_V_SCALED", "SRS_COGNITION",
       "FIQ_TEST_TYPE", "WISC_IV_PSI", "OFF_STIMULANTS_AT_SCAN", "VINELAND_PLAY_V_SCALED", "AGE_AT_MPRAGE",
       "VIQ_TEST_TYPE", "ADI_RRB_TOTAL_C", "WISC_IV_DIGIT_SPAN_SCALED", "FIQ", "DSM_IV_TR", "DX_GROUP",
       "VINELAND_INTERPERSONAL_V_SCALED", "VINELAND_SUM_SCORES", "ADOS_STEREO_BEHAV", "ADI_R_ONSET_TOTAL_D",
       "ADOS_GOTHAM_SOCAFFECT", "ADOS_GOTHAM_RRB", "CURRENT_MED_STATUS", "VINELAND_EXPRESSIVE_V_SCALED",
       "AGE_AT_SCAN", "WISC_IV_PRI", "SEX", "SRS_RAW_TOTAL", "ADOS_RSRCH_RELIABLE", "WISC_IV_SIM_SCALED",
       "WISC_IV_CODING_SCALED", "SRS_MANNERISMS", "AQ_TOTAL", "HANDEDNESS_SCORES", "HANDEDNESS_CATEGORY",
       "SRS_VERSION", "ADI_R_RSRCH_RELIABLE", "EYE_STATUS_AT_SCAN", "MEDICATION_NAME", "ADOS_SOCIAL",
       "ADOS_MODULE", "VINELAND_RECEPTIVE_V_SCALED", "VINELAND_DAILYLVNG_STANDARD", "VINELAND_ABC_STANDARD",
       "PIQ", "VINELAND_SOCIAL_STANDARD", "SITE_ID", "COMORBIDITY", "BMI", "VINELAND_COMMUNITY_V_SCALED",
       "ADOS_TOTAL", "VINELAND_INFORMANT", "WISC_IV_WMI", "WISC_IV_MATRIX_SCALED", "WISC_IV_LET_NUM_SCALED",
       "PIQ_TEST_TYPE", "SRS_COMMUNICATION", "WISC_IV_VOCAB_SCALED", "SRS_AWARENESS", "WISC_IV_PIC_CON_SCALED",
       "SRS_MOTIVATION"
     ]
   }

**Get Left-Pallidum volume (fsl_0000012) values for all subjects in a project**
.. code-block:: HTML

   pynidm query -nl ttl/cmu_a.ttl -u /projects/cc305b3e-67aa-11ea-ba45-003ee1ce9545?fields=fsl_000012

.. code-block:: HTML

   <pre>
   -----------------------------------------------  -----------------------------------------------------
   AcquisitionModality                              ["MagneticResonanceImaging"]
   ImageContrastType                                ["FlowWeighted", "T1Weighted"]
   ImageUsageType                                   ["Functional", "Anatomical"]
   Task                                             ["rest"]
   sio:Identifier                                   "1.0.1"
   dctypes:title                                    "ABIDE CMU_a Site"
   http://www.w3.org/1999/02/22-rdf-syntax-ns#type  "http://www.w3.org/ns/prov#Activity"
   prov:Location                                    "file://datasets.datalad.org/abide/RawDataBIDS/CMU_a"
   -----------------------------------------------  -----------------------------------------------------

   subjects
   ------------------------------------
   fdb6c8bc-67aa-11ea-ba45-003ee1ce9545
   b276ebb6-67aa-11ea-ba45-003ee1ce9545
   a38c4e42-67aa-11ea-ba45-003ee1ce9545
   a2ff751c-67aa-11ea-ba45-003ee1ce9545
   cfce5728-67aa-11ea-ba45-003ee1ce9545
   f165e7ae-67aa-11ea-ba45-003ee1ce9545
   cf4605ee-67aa-11ea-ba45-003ee1ce9545
   a1efa78c-67aa-11ea-ba45-003ee1ce9545
   d0de8ebc-67aa-11ea-ba45-003ee1ce9545
   a4a999ba-67aa-11ea-ba45-003ee1ce9545
   a0555098-67aa-11ea-ba45-003ee1ce9545
   b41d75f2-67aa-11ea-ba45-003ee1ce9545
   be3fbff0-67aa-11ea-ba45-003ee1ce9545
   eec5a0ca-67aa-11ea-ba45-003ee1ce9545

   data_elements
   -------------------------------
   SCQ_TOTAL
   VIQ
   ...
   WISC_IV_PIC_CON_SCALED
   SRS_MOTIVATION

   subject                               field       datumType    label                   value  units
   ------------------------------------  ----------  -----------  --------------------  -------  -------
   fdb6c8bc-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1630  mm^3
   b276ebb6-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     2062  mm^3
   a38c4e42-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1699  mm^3
   a2ff751c-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1791  mm^3
   cfce5728-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     2017  mm^3
   f165e7ae-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     2405  mm^3
   cf4605ee-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     2062  mm^3
   a1efa78c-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1961  mm^3
   d0de8ebc-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1568  mm^3
   a4a999ba-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1948  mm^3
   a0555098-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1764  mm^3
   b41d75f2-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     2031  mm^3
   be3fbff0-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1935  mm^3
   eec5a0ca-67aa-11ea-ba45-003ee1ce9545  fsl_000012  ilx_0738276  Left-Pallidum (mm^3)     1806  mm^3
   </pre>

**Get the subjects in a project:**

.. code-block:: HTML

   pynidm query -nl "cmu_a.nidm.ttl" -u http://localhost:5000/projects/dc1bf9be-10a3-11ea-8779-003ee1ce9545/subjects

Example response:

.. code-block:: JSON

   deef8eb2-10a3-11ea-8779-003ee1ce9545
   df533e6c-10a3-11ea-8779-003ee1ce9545
   ddbfb454-10a3-11ea-8779-003ee1ce9545
   df21cada-10a3-11ea-8779-003ee1ce9545
   dcfa35b2-10a3-11ea-8779-003ee1ce9545
   de89ce4c-10a3-11ea-8779-003ee1ce9545
   dd2ce75a-10a3-11ea-8779-003ee1ce9545
   ddf21020-10a3-11ea-8779-003ee1ce9545
   debc0f74-10a3-11ea-8779-003ee1ce9545
   de245134-10a3-11ea-8779-003ee1ce9545
   dd5f2f30-10a3-11ea-8779-003ee1ce9545
   dd8d4faa-10a3-11ea-8779-003ee1ce9545
   df87cbaa-10a3-11ea-8779-003ee1ce9545
   de55285e-10a3-11ea-8779-003ee1ce9545


**Use the command line to get statistics on a project for the AGE_AT_SCAN and a FSL data element:**

.. code-block:: HTML

   pynidm query -nl ttl/cmu_a.nidm.ttl -u /statistics/projects/dc1bf9be-10a3-11ea-8779-003ee1ce9545?fields=instruments.AGE_AT_SCAN,derivatives.fsl_000001

Example response:


.. code-block:: bash

  -------------------------------------------------  ---------------------------------------------
  "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"  http://www.w3.org/ns/prov#Activity
  "title"                                            ABIDE CMU_a Site
  "Identifier"                                       1.0.1
  "prov:Location"                                    /datasets.datalad.org/abide/RawDataBIDS/CMU_a
  "NIDM_0000171"                                     14
  "age_max"                                          33.0
  "age_min"                                          21.0

    gender
  --------
         1
         2

  handedness
  ------------
  R
  L
  Ambi

  subjects
  ------------------------------------
  de89ce4c-10a3-11ea-8779-003ee1ce9545
  deef8eb2-10a3-11ea-8779-003ee1ce9545
  dd8d4faa-10a3-11ea-8779-003ee1ce9545
  ddbfb454-10a3-11ea-8779-003ee1ce9545
  de245134-10a3-11ea-8779-003ee1ce9545
  debc0f74-10a3-11ea-8779-003ee1ce9545
  dd5f2f30-10a3-11ea-8779-003ee1ce9545
  ddf21020-10a3-11ea-8779-003ee1ce9545
  dcfa35b2-10a3-11ea-8779-003ee1ce9545
  df21cada-10a3-11ea-8779-003ee1ce9545
  df533e6c-10a3-11ea-8779-003ee1ce9545
  de55285e-10a3-11ea-8779-003ee1ce9545
  df87cbaa-10a3-11ea-8779-003ee1ce9545
  dd2ce75a-10a3-11ea-8779-003ee1ce9545

  -----------  ------------------  --------
  AGE_AT_SCAN  max                 33
  AGE_AT_SCAN  min                 21
  AGE_AT_SCAN  median              26
  AGE_AT_SCAN  mean                26.2857
  AGE_AT_SCAN  standard_deviation   4.14778
  -----------  ------------------  --------

  ----------  ------------------  -----------
  fsl_000001  max                 1.14899e+07
  fsl_000001  min                 5.5193e+06
  fsl_000001  median              7.66115e+06
  fsl_000001  mean                8.97177e+06
  fsl_000001  standard_deviation  2.22465e+06
  ----------  ------------------  -----------

**Get details on a subject. Use -j for a JSON formatted resonse:**

.. code-block:: HTML

   pynidm query -j -nl "cmu_a.nidm.ttl" -u http://localhost:5000/projects/dc1bf9be-10a3-11ea-8779-003ee1ce9545/subjects/df21cada-10a3-11ea-8779-003ee1ce9545

Example response:

.. code-block:: JSON

   {
  "uuid": "df21cada-10a3-11ea-8779-003ee1ce9545",
  "id": "0050665",
  "activity": [
    "e28dc764-10a3-11ea-a7d3-003ee1ce9545",
    "df28e95a-10a3-11ea-8779-003ee1ce9545",
    "df21c76a-10a3-11ea-8779-003ee1ce9545"
  ],
  "instruments": {
    "e28dd218-10a3-11ea-a7d3-003ee1ce9545": {
      "SRS_VERSION": "nan",
      "ADOS_MODULE": "nan",
      "WISC_IV_VCI": "nan",
      "WISC_IV_PSI": "nan",
      "ADOS_GOTHAM_SOCAFFECT": "nan",
      "VINELAND_PLAY_V_SCALED": "nan",
      "null": "http://www.w3.org/ns/prov#Entity",
      "VINELAND_EXPRESSIVE_V_SCALED": "nan",
      "SCQ_TOTAL": "nan",
      "SRS_MOTIVATION": "nan",
      "PIQ": "104.0",
      "FIQ": "109.0",
      "WISC_IV_PRI": "nan",
      "FILE_ID": "CMU_a_0050665",
      "VIQ": "111.0",
      "WISC_IV_VOCAB_SCALED": "nan",
      "VINELAND_DAILYLVNG_STANDARD": "nan",
      "WISC_IV_SIM_SCALED": "nan",
      "WISC_IV_DIGIT_SPAN_SCALED": "nan",
      "AGE_AT_SCAN": "33.0"
      }
   },
  "derivatives": {
      "b9fe0398-16cc-11ea-8729-003ee1ce9545": {
         "URI": "http://iri.nidash.org/b9fe0398-16cc-11ea-8729-003ee1ce9545",
         "values": {
           "http://purl.org/nidash/fsl#fsl_000005": {
             "datumType": "ilx_0102597",
             "label": "Left-Amygdala (voxels)",
             "value": "1573",
             "units": "voxel"
           },
           "http://purl.org/nidash/fsl#fsl_000004": {
             "datumType": "ilx_0738276",
             "label": "Left-Accumbens-area (mm^3)",
             "value": "466.0",
             "units": "mm^3"
           },
           "http://purl.org/nidash/fsl#fsl_000003": {
             "datumType": "ilx_0102597",
             "label": "Left-Accumbens-area (voxels)",
             "value": "466",
             "units": "voxel"
           }
         },
         "StatCollectionType": "FSLStatsCollection"
      }
   }
