# LOCAL NETWORK TEST GUIDE

## DESCRIPTION
Considering there are several worker machines and a master machine in our local network. In this example we used Windows 11 machine with Ubuntu 26.04 WSL instance as master, Raspberry Pi 5 (4 GB) machine with Ubuntu 24.04 as worker, Raspberry Pi 5 (8 GB) machine with Ubuntu 24.04 as another worker.

## PREREQUISITES
This guide assumes that this repo is cloned to all the mentioned machines and that the corresponding PARCS docker image is built with:
```
docker build -t parcs-node .
```


## ALIASES
All the described values here are just aliases, not the actual ip addresses and users.<br>

Let `<MASTER_IP>` be the ip address of the master host machine (Windows, not WSL internal).<br>
Let `<WORKER1_IP>` be the ip address of the Raspberry Pi 5 (4 GB) machine.<br>
Let `<WORKER2_IP>` be the ip address of the Raspberry Pi 5 (8 GB) machine.<br>
Let `<WORKER_IP>` be the ip address of the remote worker machine in general.<br>
Let `<USER>` be the Windows user.<br>


## GUIDE
### 1. CONFIGURE WSL FOR INCOMING CONNECTIONS
Stop WSL (if running):
```
wsl --shutdown
```

Create (or edit) in user directory `C:\Users\<USER>\.wslconfig` file with next content:
```
[wsl2]
networkingMode=mirrored
```

Re-open the WSL Ubuntu distribution again, for example from Windows Terminal or VS Code.

Create Hyper-V firewall rule (as administrator on host Windows):
```
New-NetFirewallHyperVRule `
  -Name "PARCS-WSL-HTTP-8080" `
  -DisplayName "Temporary PARCS WSL HTTP 8080" `
  -Direction Inbound `
  -VMCreatorId "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}" `
  -Protocol TCP `
  -LocalPorts 8080
```

Verify that new rule exists:
```
Get-NetFirewallHyperVRule `
  -VMCreatorId "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}" |
  Where-Object Name -eq "PARCS-WSL-HTTP-8080"
```

After you do all your parcs labs (not now), don't forget to remove this firewall rule (as administrator on host Windows):
```
Remove-NetFirewallHyperVRule -Name "PARCS-WSL-HTTP-8080"
```

Get host Windows ip address `<MASTER_IP>`:
```
ipconfig
```

Verify WSL ip address:
```
ip addr
```

`<MASTER_IP>` is the LAN IPv4 address of the Windows host from `ipconfig`.
Do not use a WSL-internal address such as `172.x.x.x`.


### 2. VERIFY WSL IS ACCESSIBLE FROM REMOTE
Start simple local server (in WSL):
```
python3 -m http.server 8080 --bind 0.0.0.0
```

Check server access (from remote):
```
curl -v http://<MASTER_IP>:8080/
```
Should return `HTTP 200`.

Stop the local server with `Ctrl + C` (in WSL)


### 3. VERIFY MASTER NODE IN WSL IS ACCESSIBLE FROM REMOTE
Start master container (in WSL):
```
docker run -d \
  --name parcs-master \
  -p 8080:8080 \
  -e PARCS_NODE_ROLE=master \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  parcs-node:latest
```

Check the PARCS web page in a browser at `http://localhost:8080/`.

Check docker master node is accessible from remote:
```
curl -v http://<MASTER_IP>:8080/api/internal/heartbeat
```
Should return `HTTP 200`.


### 4. VERIFY MASTER NODE IN WSL IS ACCESSIBLE FROM WORKER NODE ON REMOTE
Get worker ip address `<WORKER_IP>` (on remote):
```
ip addr
```

Create environment variables for convenience (on remote):
```
WRKR_LAN_IP=<WORKER_IP>
MSTR_LAN_IP=<MASTER_IP>

echo $WRKR_LAN_IP $MSTR_LAN_IP
```

Start worker container (on remote):
```
docker run -d \
  --name parcs-worker \
  -p 8080:8080 \
  -p 9090:9090 \
  -e PARCS_NODE_ROLE=worker \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_ADVERTISE_HOST="$WRKR_LAN_IP" \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  -e PARCS_MASTER_HOST="$MSTR_LAN_IP" \
  -e PARCS_MASTER_PORT=8080 \
  parcs-node:latest
```

Check in web browser `Nodes` page at `http://localhost:8080/workers` (the worker should be registered).

Check worker is accessible from master:
```
curl -v http://<WORKER_IP>:8080/api/internal/heartbeat
```
Note: TCP 9090 may return "Connection refused" while no job is running.
PARCS opens the Pyro5 RPC server for the worker only during job execution.


### 5. SETTING THE ENVIRONMENT FOR LABS
Considering you've tested all previous steps and verified that master and worker nodes are accessible. Now we do all the same for our existing remote machines (Raspberry Pi boards).

Remove existing container from previous session if exists (in WSL):
```
docker rm -f parcs-master 2>/dev/null || true
```

Start master node (in WSL):
```
docker run -d \
  --name parcs-master \
  -p 8080:8080 \
  -e PARCS_NODE_ROLE=master \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  parcs-node:latest
```

Remove existing container from previous session if exists (on first board):
```
docker rm -f parcs-worker 2>/dev/null || true
```

Start worker-1 node (on first board):
```
WRKR_LAN_IP=<WORKER1_IP>
MSTR_LAN_IP=<MASTER_IP>

docker run -d \
  --name parcs-worker \
  -p 8080:8080 \
  -p 9090:9090 \
  -e PARCS_NODE_ROLE=worker \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_ADVERTISE_HOST="$WRKR_LAN_IP" \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  -e PARCS_MASTER_HOST="$MSTR_LAN_IP" \
  -e PARCS_MASTER_PORT=8080 \
  parcs-node:latest
```

Remove existing container from previous session if exists (on second board):
```
docker rm -f parcs-worker 2>/dev/null || true
```

Start worker-2 node (on second board):
```
WRKR_LAN_IP=<WORKER2_IP>
MSTR_LAN_IP=<MASTER_IP>

docker run -d \
  --name parcs-worker \
  -p 8080:8080 \
  -p 9090:9090 \
  -e PARCS_NODE_ROLE=worker \
  -e PARCS_BIND_HOST=0.0.0.0 \
  -e PARCS_ADVERTISE_HOST="$WRKR_LAN_IP" \
  -e PARCS_HTTP_PORT=8080 \
  -e PARCS_RPC_PORT=9090 \
  -e PARCS_MASTER_HOST="$MSTR_LAN_IP" \
  -e PARCS_MASTER_PORT=8080 \
  parcs-node:latest
```

Check PARCS web page in browser at `http://localhost:8080/` (in web browser).

Verify workers `worker-1` and `worker-2` are registered.

Add your solution and data on `Add Job` page at `http://localhost:8080/add_job`.

Get output and job status on `Jobs` page at `http://localhost:8080/jobs`.

Stop and remove the worker-1 node (on first board):
```
docker rm -f parcs-worker
```

Stop and remove the worker-2 node (on second board):
```
docker rm -f parcs-worker
```

Stop and remove the master node (in WSL):
```
docker rm -f parcs-master
```
