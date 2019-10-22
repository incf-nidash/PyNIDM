#!/bin/bash

sudo docker build -f Dockerfile -t pynidm .
sudo docker build -f Dockerfile-rest -t pynidm-rest .