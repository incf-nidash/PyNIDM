FROM ubuntu:18.04

RUN apt-get update &&  \
    apt-get install -y git python3 graphviz python3-pip ssh mercurial python-setuptools zip

RUN python3 -m pip install --upgrade pip && \
    pip3 install rdflib requests rapidfuzz fuzzywuzzy pygithub pybids duecredit setuptools \
                 python-Levenshtein pytest graphviz prov pydot validators ontquery \
                 click rdflib-jsonld pyld pytest-cov tabulate joblib



WORKDIR /opt

RUN wget https://files.pythonhosted.org/packages/af/1c/7e4c25d5539ac8979d633afe03d16ddb01716c6cde97ebea33a6659ea9c6/Owlready2-0.24.tar.gz&& \
    tar -xzf Owlready2-0.24.tar.gz && \
    cd Owlready2-0.24 && \
    python setup.py build && \
    python setup.py install

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN update-alternatives --remove python /usr/bin/python2 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 10 && \
    update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 10

RUN cd / && \
    git clone https://github.com/incf-nidash/PyNIDM.git && \
    mv PyNIDM PyNIDM-snapshot && \
    cd PyNIDM-snapshot && \
    pip install -e .

RUN git config --global user.name "docker user" && git config --global user.email "docker@example.com"

ENV TMPDIR=/opt/project/cache

COPY . .

