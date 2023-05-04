FROM python:3.11
RUN apt-get update && apt-get install -y graphviz
WORKDIR /opt
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
RUN pip install git+https://github.com/incf-nidash/PyNIDM.git
RUN git config --global user.name "docker user" && \
    git config --global user.email "docker@example.com"
CMD ["/bin/bash"]
