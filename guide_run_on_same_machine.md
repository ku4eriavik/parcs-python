# SAME MACHINE TEST GUIDE

## DESCRIPTION
Considering you will start the master node as well as all the worker nodes on a same machine. In this example we used Windows 11 machine with Ubuntu 26.04 WSL instance to run all the nodes.

## PREREQUISITES
This guide assumes that this repo is cloned to WSL instance and that the corresponding PARCS docker image is built with:
```
docker build -t parcs-node .
```
Currrently, the `dev/refactor_legacy` repo branch is used.


## GUIDE
Create the dedicated network (or reuse if exists):
```
docker network inspect parcs-network >/dev/null 2>&1 || docker network create parcs-network
```

Start the master node:
```
docker rm -f parcs-master 2>/dev/null || true

docker run -d \
  --name parcs-master \
  --network parcs-network \
  -p 8080:8080 \
  -e PARCS_NODE_ROLE=master \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  parcs-node:latest
```

Open the PARCS page in web browser at `http://localhost:8080/`.

Start the worker-1 node:
```
docker rm -f parcs-worker-1 2>/dev/null || true

docker run -d \
  --name parcs-worker-1 \
  --network parcs-network \
  -e PARCS_NODE_ROLE=worker \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_ADVERTISE_HOST=parcs-worker-1 \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  -e PARCS_MASTER_HOST=parcs-master \
  -e PARCS_MASTER_PORT=8080 \
  parcs-node:latest
```

Start the worker-2 node:
```
docker rm -f parcs-worker-2 2>/dev/null || true

docker run -d \
  --name parcs-worker-2 \
  --network parcs-network \
  -e PARCS_NODE_ROLE=worker \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_ADVERTISE_HOST=parcs-worker-2 \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  -e PARCS_MASTER_HOST=parcs-master \
  -e PARCS_MASTER_PORT=8080 \
  parcs-node:latest
```

Start the worker-... node:<br>
...and so on for all the worker nodes.

Verify workers are registered on `Nodes` page at `http://localhost:8080/workers`.

Add your solution and data on `Add Job` page at `http://localhost:8080/add_job`.

Get output and job status on `Jobs` page at `http://localhost:8080/jobs`.

Stop and remove the nodes:
```
docker rm -f \
  parcs-master \
  parcs-worker-1 \
  parcs-worker-2 \

  ... and so on for all the worker nodes.
```

Remove the network:
```
docker network rm parcs-network
```
