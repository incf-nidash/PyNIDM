#!/bin/bash
#
#  You can create the docker container with the build.sh script in this directory
#
# The command below will mount the ~/PyNIDM and ~/simple2_NIDM_examples directories
# in /opt and give you a bash shell in the container

sudo docker run -v ~/PyNIDM:/opt/project -v ~/simple2_NIDM_examples:/opt/simple2_NIDM_examples  -it pynidm
