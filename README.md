# PyNIDM

## This is WIP, but here is the instruction to install PyNIDM with conda on OSX that should work:
 
* `cd PyNIDM`
* `conda create -n pynidm_py35 python=3.5`
* `source activate pynidm_py35`
* `pip install -e .`
* `conda install pydot`
* `conda install graphviz`

And you can test if it works:
* `python nidm/experiment/tests/test_experiment.py`
