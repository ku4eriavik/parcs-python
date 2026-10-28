# GOOGLE CLOUD TEST GUIDE

## DESCRIPTION
This guide describes how to deploy and test PARCS in the Google Cloud environment.

All Google Cloud CLI commands in this guide were executed from an Ubuntu 26.04 WSL instance on a Windows 11 host. The guide creates one master node and multiple worker nodes as Ubuntu 24.04 Compute Engine virtual machines in the same Google Cloud zone.

Each VM clones the PARCS repository, builds the Docker image locally, and runs the appropriate PARCS node container. The master and workers communicate through their private VPC IP addresses, while the master web interface is accessed through its external IP address.

This guide uses the `default` VPC for simplicity and short-lived isolated tests. The default VPC contains broader predefined firewall rules, including internal traffic between VMs. For production or a shared project, create a dedicated custom VPC and allow only the required PARCS ports and administrative access.

This guide was tested with `e2-medium` instances. Available machine types, quotas, and prices can differ by project and zone. Review the available machine types and select one appropriate for your test before creating instances.

### USEFUL GOOGLE CLOUD CONSOLE LINKS
- [Project dashboard](https://console.cloud.google.com/home/dashboard?project=<YOUR_PROJECT_ID>)
- [Compute Engine overview](https://console.cloud.google.com/compute/overview?project=<YOUR_PROJECT_ID>)

**Note:** replace `<YOUR_PROJECT_ID>` with the actual Google Cloud project ID.
These pages are useful for checking billing, APIs, VM status, external IP addresses, disks, and firewall rules.


## ALIASES
All the described fields here are just aliases, not the actual values.<br>

Let `<YOUR_PROJECT_ID>` be the name of your project.<br>
Let `<YOUR_BILLING_ACCOUNT_ID>` be your billing account id (`"XXXXXX-XXXXXX-XXXXXX"` format).<br>


## PREREQUISITES
A Google Cloud account must be created.<br>
A valid, active billing account must be available and linked to the project before creating Compute Engine resources.<br>
Google Cloud SDK should be installed.<br>


## GUIDE
### 1. AUTHORIZATION
Login to Google Cloud:
```
gcloud auth login
```

If the browser does not open automatically from WSL:
```
gcloud auth login --no-launch-browser
```

You can verify you are logged in with:
```
gcloud auth list
```


### 2. PROJECT SETTINGS
Create new project if needed (or move to next step if exists). The project ID must be globally unique:
```
export PROJECT_ID="<YOUR_PROJECT_ID>"
gcloud projects create "$PROJECT_ID"
```

Then set the same project ID:
```
gcloud config set project "$PROJECT_ID"
```

List your billing accounts:
```
gcloud billing accounts list --filter="open=true"
```

Set your billing account to the project:
```
export BILLING_ACCOUNT_ID=<YOUR_BILLING_ACCOUNT_ID>
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID"
```

Verify project now has billing account:
```
gcloud billing projects describe "$PROJECT_ID"
```

Set compute region:
```
export REGION="europe-north1"
gcloud config set compute/region "$REGION"
```

Set compute zone:
```
export ZONE="europe-north1-a"
gcloud config set compute/zone "$ZONE"
```

Enable computing API:
```
gcloud services enable compute.googleapis.com
```


### 3. FIREWALL RULES
Set network environment variable:
```
export NETWORK="default"
```

Verify that the selected network exists (`default` should exist in most new projects):
```
gcloud compute networks describe "$NETWORK" --project="$PROJECT_ID"
```

Create firewall rule for internal PARCS traffic between master and workers:
```
gcloud compute firewall-rules create parcs-allow-internal \
  --project="$PROJECT_ID" \
  --network="$NETWORK" \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:8080,tcp:9090 \
  --source-tags=parcs-node \
  --target-tags=parcs-node
```

Export public IP:
```
export MY_PUBLIC_IP="$(curl -4 -s ifconfig.me)"
echo "$MY_PUBLIC_IP"
```

Create firewall rule that allows your current public IP address to access the master web UI:
```
gcloud compute firewall-rules create parcs-allow-master-ui \
  --project="$PROJECT_ID" \
  --network="$NETWORK" \
  --direction=INGRESS \
  --action=ALLOW \
  --rules=tcp:8080 \
  --source-ranges="${MY_PUBLIC_IP}/32" \
  --target-tags=parcs-master
```


### 4. MASTER INSTANCE CREATION AND PREPARATION
Set repo variables:
```
export REPO_URL="https://github.com/ku4eriavik/parcs-python.git"
export BRANCH="master"
```

Create master instance:
```
export MASTER="parcs-master"

gcloud compute instances create "$MASTER" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --machine-type=e2-medium \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --network="$NETWORK" \
  --tags=parcs-node,parcs-master
```

Wait until it is running, then prepare it:
```
gcloud compute ssh "$MASTER" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --command="
    sudo apt-get update &&
    sudo apt-get install -y docker.io git &&
    sudo systemctl enable --now docker &&
    rm -rf parcs-python &&
    git clone --branch '$BRANCH' '$REPO_URL' parcs-python &&
    cd parcs-python &&
    sudo docker build -t parcs-node:latest .
  "
```

Check that the docker image was built:
```
gcloud compute ssh "$MASTER" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --command="sudo docker image ls parcs-node"
```

Get and retain the master’s internal IP for the worker startup step later:
```
export MASTER_IP="$(
  gcloud compute instances describe "$MASTER" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --format='get(networkInterfaces[0].networkIP)'
)"

echo "Master internal IP: $MASTER_IP"
```


### 5. WORKER INSTANCES CREATION AND PREPARATION
Create worker instances:
```
export WORKERS="parcs-worker-1 parcs-worker-2 parcs-worker-3 parcs-worker-4"

for worker in $WORKERS; do
  gcloud compute instances create "$worker" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --machine-type=e2-medium \
    --image-family=ubuntu-2404-lts-amd64 \
    --image-project=ubuntu-os-cloud \
    --network="$NETWORK" \
    --tags=parcs-node
done
```

Prepare each worker:
```
for worker in $WORKERS; do
  echo "Preparing $worker..."

  gcloud compute ssh "$worker" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --command="
      sudo apt-get update &&
      sudo apt-get install -y docker.io git &&
      sudo systemctl enable --now docker &&
      rm -rf parcs-python &&
      git clone --branch '$BRANCH' '$REPO_URL' parcs-python &&
      cd parcs-python &&
      sudo docker build -t parcs-node:latest .
    "

  gcloud compute ssh "$worker" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --command="sudo docker image ls parcs-node"
done
```


### 6. VERIFY INSTANCES ARE PREPARED
Verify all instances and their internal addresses:
```
gcloud compute instances list \
  --project="$PROJECT_ID" \
  --filter="name~'^parcs-(master|worker-)'" \
  --format="table(name,status,networkInterfaces[0].networkIP,networkInterfaces[0].accessConfigs[0].natIP)"
```


### 7. RUN PARCS CONTAINERS
Start master container:
```
gcloud compute ssh "$MASTER" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --command="
    sudo docker rm -f parcs-master 2>/dev/null || true &&
    sudo docker run -d \
      --name parcs-master \
      --restart unless-stopped \
      --network host \
      -e PARCS_NODE_ROLE=master \
      -e PARCS_BIND_HOST=0.0.0.0 \
      -e PARCS_HTTP_PORT=8080 \
      -e PARCS_RPC_PORT=9090 \
      parcs-node:latest
  "
```

Get master external IP address - this one to open in browser later:
```
export MASTER_EXTERNAL_IP="$(
  gcloud compute instances describe "$MASTER" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
)"

echo "http://${MASTER_EXTERNAL_IP}:8080"
```

Start worker containers:
```
for worker in $WORKERS; do
  WORKER_IP="$(
    gcloud compute instances describe "$worker" \
      --project="$PROJECT_ID" \
      --zone="$ZONE" \
      --format='get(networkInterfaces[0].networkIP)'
  )"

  echo "$worker: $WORKER_IP"

  gcloud compute ssh "$worker" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --command="
      sudo docker rm -f parcs-worker 2>/dev/null || true &&
      sudo docker run -d \
        --name parcs-worker \
        --restart unless-stopped \
        --network host \
        -e PARCS_NODE_ROLE=worker \
        -e PARCS_BIND_HOST=0.0.0.0 \
        -e PARCS_ADVERTISE_HOST='$WORKER_IP' \
        -e PARCS_HTTP_PORT=8080 \
        -e PARCS_RPC_PORT=9090 \
        -e PARCS_MASTER_HOST='$MASTER_IP' \
        -e PARCS_MASTER_PORT=8080 \
        parcs-node:latest
    "
done
```

Open PARCS web page in browser at: `http://${MASTER_EXTERNAL_IP}:8080`.

Verify all workers are registered on `Nodes` page at `http://${MASTER_EXTERNAL_IP}:8080/workers`.


### 8. PROCESS SOLUTION WITH PARCS
Add job on `Add Job` page at `http://${MASTER_EXTERNAL_IP}:8080/add_job`.

Get results and statistics on `Jobs` page at `http://${MASTER_EXTERNAL_IP}:8080/jobs`.

Play with input parameters and amount of workers to get different processing time. To run computations on less amount of workers simply disable some workers on `Nodes` page at `http://${MASTER_EXTERNAL_IP}:8080/workers`. You can re-enable them here as well.


### 9. CLEAN UP EVERYTHING AFTER USE
Stop and remove worker containers:
```
for worker in $WORKERS; do
  gcloud compute ssh "$worker" \
    --project="$PROJECT_ID" \
    --zone="$ZONE" \
    --command="sudo docker rm -f parcs-worker 2>/dev/null || true"
done
```

Stop and remove master container:
```
gcloud compute ssh "$MASTER" \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --command="sudo docker rm -f parcs-master 2>/dev/null || true"
```

Stop and remove all instances:
```
gcloud compute instances delete \
  "$MASTER" $WORKERS \
  --project="$PROJECT_ID" \
  --zone="$ZONE" \
  --delete-disks=all \
  --quiet
```

Verify no PARCS instances remain:
```
gcloud compute instances list \
  --project="$PROJECT_ID" \
  --filter="name~'^parcs-(master|worker-)'"
```

Remove temporary firewall rules:
```
gcloud compute firewall-rules delete \
  parcs-allow-internal \
  parcs-allow-master-ui \
  --project="$PROJECT_ID" \
  --quiet
```

Verify they are gone:
```
gcloud compute firewall-rules list \
  --project="$PROJECT_ID" \
  --filter="name~'^parcs-allow-'"
```

For an extra check:
```
gcloud compute disks list --project="$PROJECT_ID"
```
