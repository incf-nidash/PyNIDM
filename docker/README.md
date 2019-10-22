# Docker and REST API

This dockerfile can be used to create a development docker container suitable for both
interactive use and also as a proof of concept REST API server. 

#Build the container

These instructions assume you have the PyNIDM source code in ~/PyNIDM.
To build the container, start in this directory and use the command:

```
./build.sh
```
 
## Interactive

You can then run the container interactively with:
```
./rundocker.sh
```

This will make a live mount of the files in ~/PyNIDM on your host system
in the directory /opt/PyNIDM in the container.

## REST Server

This section assumes you have the PyNIDM source code in ~/PyNIDM. You should
also put any NIDM ttl files you want the REST s     erver to process somewhere under the 
~/PyNIDM/ttl directory.  Once you have done those things, use the command:
```
./runrest.sh
```

This should start a HTTP server that is listening on port 5000 of your 
local system.  You should be able to connect to the following routes:
```
http://localhost:5000/projects
http://localhost:5000/projects/[Project-UUID]
http://localhost:5000/projects/[Project-UUID]/subjects
http://localhost:5000/projects/[Project-UUID]/subjects/[Subject-UUID]
```

After the server is started you can continue to modify the files in your
~/PyNIDM/ttl directory and those changes will immediatly be reflected in the 
REST API results.
