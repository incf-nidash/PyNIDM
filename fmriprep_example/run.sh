bidsmri2nidm -d /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/ -bidsignore -no_concepts

csv2nidm -csv /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_results_wo_ses_run_task.csv -json_map /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/fmriprep_data_dictionary.json -no_concepts -nidm /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/bids/nidm.ttl -out /Users/dbkeator/Documents/Coding/PyNIDM/fmriprep_example/nidm_with_fmriprep.ttl
