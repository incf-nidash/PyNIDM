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
* **Location:** bin/BIDSMRI2NIDM.py 

* **Description:** This program will convert a BIDS MRI dataset to a NIDM-Experiment RDF document.  It will parse phenotype information and simply store variables/values and link to the associated json data dictionary file.

* **Example 1:** No variable->term mapping, simple BIDS dataset conversion which will add nidm.ttl file to BIDS dataset and .bidsignore file:
	 BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -bidsignore
	 
* **Example 2:** No variable->term mapping, simple BIDS dataset conversion but storing nidm file somewhere else: 

	 BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -o [PATH/nidm.ttl] 

* **Example 3:** BIDS conversion with variable->term mappings, no existing mappings available, uses Interlex for terms and github for defining terms you can't find in Interlex (note, for now these two need to be used together)!  To get an Interlex API key you visit [SciCrunch](http://scicrunch.org), register for an account, then click on "MyAccount" and "API Keys" to add a new API key for your account.  Use this API Key for the -ilxkey parameter below.  This example  adds a nidm.ttl file BIDS dataset and .bidsignore file and it will by default create you a JSON mapping file which contains the variable->term mappings you defined during the interactive, iterative activity of using this tool to map your variables to terms.  The default JSON mapping file will be called nidm_json_map.json but you can also specify this explictly using the -json_map parameter (see Example 5 below): 

	 BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -ilxkey [Your Interlex key] -github [username token] -bidsignore  

* **Example 4:** BIDS conversion with variable->term mappings, no existing mappings available, uses Interlex + NIDM OWL file for terms and github, adds nidm.ttl file BIDS dataset and .bidsignore file: 

	 BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -ilxkey [Your Interlex key] -github [username token] -owl -bidsignore  

* **Example 5 (FULL MONTY):** BIDS conversion with variable->term mappings, uses JSON mapping file first then uses Interlex + NIDM OWL file for terms and github, adds nidm.ttl file BIDS dataset and .bidsignore file: 

	 BIDSMRI2NIDM.py -d [root directory of BIDS dataset] -json_map [Your JSON file] -ilxkey [Your Interlex key] -github [username token] -owl -bidsignore

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
		 
* optional arguments: 
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
						  
	-github [GITHUB [GITHUB ...]], --github [GITHUB [GITHUB ...]]
	
	                      Use -github flag with list username token(or pw) for storing locally-defined terms in a
	                      nidm-local-terms repository in GitHub.  If user doesn''t supply a token then user will be prompted for username/password.
                        
	                      Example: -github username token
						  
	-owl                  Optional flag to query nidm-experiment OWL files

**CSV2NIDM.py**
* **Location:** bin/CSV2NIDM.py 

* **Description:** This program will load in a CSV file and iterate over the header variable
names performing an elastic search of https://scicrunch.org/ for NIDM-ReproNim
tagged terms that fuzzy match the variable names. The user will then
interactively pick a term to associate with the variable name. The resulting
annotated CSV data will then be written to a NIDM data file.

* optional arguments:
  -h, --help            show this help message and exit
  
  -csv CSV_FILE         Path to CSV file to convert
  
  -ilxkey KEY           Interlex/SciCrunch API key to use for query
  
  -json_map JSON_MAP    User-suppled JSON file containing variable-term mappings.
  
  -nidm NIDM_FILE       Optional NIDM file to add CSV->NIDM converted graph to
  
  -github [GITHUB [GITHUB ...]]
                        Use -github flag with username token(or pw) for
                        storing locally-defined terms in a "nidm-local-terms"
                        repository in GitHub. If user doesnt supply a token
                        then user will be prompted for username/password.
                        Example: -github username token
						
  -owl                  Optionally searches NIDM OWL files...internet
                        connection required
						
  -out OUTPUT_FILE      Filename to save NIDM file

**nidm_query.py**
* **Location:** bin/nidm_query.py

* **Description:** This program provides query support for NIDM-Experiment files

* optional arguments:
  -h, --help            show this help message and exit
  
  -query QUERY_FILE, --nidm QUERY_FILE
                        Text file containing a SPARQL query to execute
						
  -nidm-list NIDM_LIST, --nidm-list NIDM_LIST
                        A comma separated list of NIDM files with full path
						
  -o OUTPUT_FILE, --o OUTPUT_FILE
                        Optional output file (CSV) to store results of query
						

