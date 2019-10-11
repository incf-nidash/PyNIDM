FROM ubuntu:18.04

RUN apt-get update
RUN apt-get install -y git python3 graphviz python3-pip ssh mercurial python-setuptools
RUN pip3 install  rdflib requests fuzzywuzzy pygithub pybids duecredit setuptools python-Levenshtein

WORKDIR /app
RUN hg clone https://bitbucket.org/jibalamy/owlready2
WORKDIR /app/owlready2
RUN python setup.py build && python setup.py install
WORKDIR /app

RUN pip3 install pytest graphviz prov pydot validators ontquery click rdflib-jsonld pyld

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN update-alternatives --remove python /usr/bin/python2
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 10

COPY . .

