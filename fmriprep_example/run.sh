# create nidm file from BIDS dataset
bidsmri2nidm -d /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/ -bidsignore -no_concepts

# add to existing nidm file
csv2nidm -csv /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -json_map /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.json -derivative /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -nidm /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm.ttl
pynidm visualize -nl /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm.ttl

# create new nidm file of only derivative data
csv2nidm -csv /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -json_map /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.json -derivative /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -out /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm_only_fmriprep.ttl
pynidm visualize -nl /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm_only_fmriprep.ttl

# create new nidm file using CSV version of data dictionary
csv2nidm -csv /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -csv_map /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.csv -derivative /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -out /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm_only_fmriprep_csv_dd.ttl
pynidm visualize -nl /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm_only_fmriprep_csv_dd.ttl

# add to existing nidm file using CSV version of data dictionary
bidsmri2nidm -d /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/ -bidsignore -no_concepts
csv2nidm -csv /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_v2.csv -csv_map /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.csv -derivative /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_software_metadata.csv -no_concepts -nidm /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm.ttl
pynidm visualize -nl /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm.ttl
