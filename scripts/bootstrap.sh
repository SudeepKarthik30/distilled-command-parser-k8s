#!/usr/bin/env bash
set -euo pipefail

PRIMARY_REL="${MODEL_RELEASE_URL:-https://github.com/SudeepKarthik30/distilled-command-parser-k8s/releases/download/v1.0}"

AK=$(openssl rand -hex 8)
SK=$(openssl rand -hex 16)

# Create Kubernetes namespaces
for ns in data app pipeline; do
  kubectl create ns "$ns" --dry-run=client -o yaml | kubectl apply -f -
done

# Provision credentials secret for SeaweedFS S3
cat > /tmp/s3.json << JSON
{"identities":[{"name":"admin","credentials":[{"accessKey":"$AK","secretKey":"$SK"}],"actions":["Admin","Read","Write","List","Tagging"]}]}
JSON

kubectl -n data create secret generic seaweed-s3 --from-file=s3.json=/tmp/s3.json --dry-run=client -o yaml | kubectl apply -f -
kubectl -n app create secret generic s3-creds --from-literal=S3_ACCESS_KEY="$AK" --from-literal=S3_SECRET_KEY="$SK" --dry-run=client -o yaml | kubectl apply -f -
rm -f /tmp/s3.json

# Deploy SeaweedFS
kubectl apply -f k8s/seaweedfs.yaml
kubectl -n data rollout status deploy/seaweedfs --timeout=300s

# Prepare model weights
WORK_DIR=$(mktemp -d)
for v in v1 v2; do
  ZIP_NAME="model_${v}.zip"
  if [ -f "./${ZIP_NAME}" ]; then
    echo "Using pre-cached ./${ZIP_NAME}"
    cp "./${ZIP_NAME}" "$WORK_DIR/${ZIP_NAME}"
  elif curl -fsSL -o "$WORK_DIR/${ZIP_NAME}" "$PRIMARY_REL/${ZIP_NAME}"; then
    echo "Downloaded ${ZIP_NAME} from release endpoint: $PRIMARY_REL"
  else
    echo "Error: ${ZIP_NAME} not found locally or at $PRIMARY_REL"
    exit 1
  fi
  unzip -q -o "$WORK_DIR/${ZIP_NAME}" -d "$WORK_DIR"
done

# Establish background port-forward to SeaweedFS S3 endpoint
kubectl -n data port-forward svc/seaweedfs 8333:8333 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null' EXIT

# Health check S3 port
for i in $(seq 30); do
  curl -s http://localhost:8333 >/dev/null && break
  sleep 2
done
curl -s http://localhost:8333 >/dev/null || { echo "SeaweedFS port-forward unreachable"; exit 1; }

export AK SK WORK_DIR
python3 - << 'PY'
import boto3
import glob
import os

s3_client = boto3.client(
    "s3",
    endpoint_url="http://localhost:8333",
    aws_access_key_id=os.environ["AK"],
    aws_secret_access_key=os.environ["SK"],
    region_name="us-east-1"
)

for bucket_name in ("datasets", "models"):
    try:
        s3_client.create_bucket(Bucket=bucket_name)
    except Exception as exc:
        print(f"Bucket notice ({bucket_name}): {exc}")

s3_client.upload_file("data/commands_pool.jsonl", "datasets", "commands_pool.jsonl")

work_dir = os.environ["WORK_DIR"]
for version_tag in ("v1", "v2"):
    model_files = glob.glob(os.path.join(work_dir, version_tag, "*"))
    for file_path in model_files:
        dest_key = f"models/{version_tag}/{os.path.basename(file_path)}"
        s3_client.upload_file(file_path, "models", dest_key)

print("SeaweedFS initialization complete: datasets and models staged successfully.")
PY
