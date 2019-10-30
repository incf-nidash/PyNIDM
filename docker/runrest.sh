#!/bin/bash
#
#  You can create the docker container with:
#  docker build -t pynidm .
#
# The command below will mount the ~/PyNIDM and ~/simple2_NIDM_examples directories
# in /opt and give you a bash shell in the container

sudo docker run -p 5000:5000 -v ~/PyNIDM:/opt/project pynidm-rest
