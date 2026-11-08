CONFIG ?= training/config.yaml
CLUSTER ?= cloudproj
IMAGE ?= command-parser:v1.0

.PHONY: all up cluster storage app test train down clean

all: up

up: cluster storage app

cluster:
	@echo "==> Creating k3d cluster from cluster/k3d.yaml..."
	k3d cluster create --config cluster/k3d.yaml
	kubectl wait --for=condition=Ready node --all --timeout=180s

storage:
	@echo "==> Initializing namespaces and SeaweedFS object storage..."
	bash scripts/bootstrap.sh

app:
	@echo "==> Building and deploying inference service image ($(IMAGE))..."
	docker build -t $(IMAGE) .
	k3d image import $(IMAGE) -c $(CLUSTER)
	kubectl apply -f k8s/deployment.yaml -f k8s/service.yaml -f k8s/ingress.yaml -f k8s/hpa.yaml
	kubectl -n app rollout status deploy/parser --timeout=600s

test:
	pytest -q tests
	python tools/nacl_sim.py network/nacl.json network/packets_sample.jsonl --check

train:
	python training/train.py --config $(CONFIG) $(if $(SUBSET),--subset $(SUBSET),)

down:
	@echo "==> Tearing down k3d cluster..."
	k3d cluster delete $(CLUSTER)

clean:
	rm -rf models/subset-test training/loss_subset.csv
