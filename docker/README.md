# Docker and REST API

This Dockerfile can be used to create a development Docker container suitable
for both interactive use and also as a proof-of-concept REST API server.

## Build the container

To build the container, start in this directory and run the commands:

```
docker build -f Dockerfile -t pynidm .
docker build -f Dockerfile-rest -t pynidm-rest .
```

## Interactive

You can then run the container interactively with a command like:

```
docker run -it -v ~/PyNIDM:/opt/project pynidm
```

This will make a live mount of the files in `~/PyNIDM` on your host system in
the directory `/opt/project` in the container.

## REST Server

This section assumes you have any NIDM ttl files you want the REST server to
process stored under `ttl/` in the current directory.  Then, use the command:

```
docker run -it -p 5000:5000 -v "$PWD/ttl":/opt/project/ttl pynidm-rest
```

This should start an HTTP server that is listening on port 5000 of your
local system.  You should be able to connect to the following routes:

```
http://localhost:5000/projects
http://localhost:5000/projects/[Project-UUID]
http://localhost:5000/projects/[Project-UUID]/subjects
http://localhost:5000/projects/[Project-UUID]/subjects/[Subject-UUID]
```

After the server is started you can continue to modify the files in your `ttl/`
directory, and those changes will immediately be reflected in the REST API
results.
