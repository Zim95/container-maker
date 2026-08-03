# Variables
include env.mk

# Development
dev_build:
	./scripts/k8s/development/k8s-development-build.sh $(USER_NAME) $(REPO_NAME)

dev_setup:
	./scripts/k8s/development/k8s-development-setup.sh $(NAMESPACE) $(HOST_DIR) $(REPO_NAME) $(REPO_PASSWORD) $(INGRESS_HOST) $(STORAGE_LAYER) $(MINIO_ENDPOINT) $(MINIO_BUCKET) $(MINIO_SECURE) $(DB_HOST) $(DB_PORT) $(DB_USERNAME) $(DB_DATABASE)

dev_teardown:
	./scripts/k8s/development/k8s-development-teardown.sh $(NAMESPACE)

# Production
prod_build:
	./scripts/k8s/deployment/k8s-development-build.sh $(USER_NAME) $(REPO_NAME)

prod_setup:
	./scripts/k8s/deployment/k8s-development-setup.sh $(NAMESPACE) $(REPO_NAME) $(REPO_PASSWORD) $(INGRESS_HOST) $(STORAGE_LAYER) $(MINIO_ENDPOINT) $(MINIO_BUCKET) $(MINIO_SECURE) $(DB_HOST) $(DB_PORT) $(DB_USERNAME) $(DB_DATABASE)

prod_teardown:
	./scripts/k8s/deployment/k8s-development-teardown.sh $(NAMESPACE)

.PHONY: dev_build dev_setup dev_teardown prod_build prod_setup prod_teardown
