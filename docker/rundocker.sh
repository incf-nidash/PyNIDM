#!/bin/bash
#
#  You can create the docker container with:
#  docker build -t pynidm .
#
# The command below will mount the ~/PyNIDM and ~/simple2_NIDM_examples directories
# in /opt and give you a bash shell in the container

sudo docker run -v ~/PyNIDM:/opt/project -v ~/simple2_NIDM_examples:/opt/simple2_NIDM_examples  -it pynidm
