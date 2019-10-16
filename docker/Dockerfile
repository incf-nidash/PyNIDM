FROM ubuntu:18.04

RUN apt-get update &&  \
    apt-get install -y git python3 graphviz python3-pip ssh mercurial python-setuptools

RUN python3 -m pip install --upgrade pip && \
    pip3 install rdflib requests fuzzywuzzy pygithub pybids duecredit setuptools \
                 python-Levenshtein pytest graphviz prov pydot validators ontquery \
                 click rdflib-jsonld pyld

WORKDIR /opt
RUN hg clone https://bitbucket.org/jibalamy/owlready2 && \
    cd owlready2 && \
    python setup.py build && \
    python setup.py install

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN update-alternatives --remove python /usr/bin/python2 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 10 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 10

# install Apache Jena
RUN apt install -y default-jdk && \
    wget http://mirrors.ibiblio.org/apache/jena/binaries/apache-jena-3.13.1.tar.gz && \
    tar -xvzf apache-jena-3.13.1.tar.gz && \
    rm /opt/apache-jena-3.13.1.tar.gz

RUN cd / && \
    git clone https://github.com/incf-nidash/PyNIDM.git && \
    mv PyNIDM PyNIDM-snapshot && \
    cd PyNIDM-snapshot && \
    pip install -e .

COPY . .

