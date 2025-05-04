# Variables
include env.mk

# Development
dev_build:
	./scripts/k8s/development/k8s-development-build.sh $(USER_NAME) $(REPO_NAME)

dev_setup:
	./scripts/k8s/development/k8s-development-setup.sh $(NAMESPACE) $(HOST_DIR) $(REPO_NAME)

dev_teardown:
	./scripts/k8s/development/k8s-development-teardown.sh $(NAMESPACE)

# Production
prod_build:
	./scripts/k8s/deployment/k8s-development-build.sh $(USER_NAME) $(REPO_NAME)

prod_setup:
	./scripts/k8s/deployment/k8s-development-setup.sh $(NAMESPACE) $(REPO_NAME)

prod_teardown:
	./scripts/k8s/deployment/k8s-development-teardown.sh $(NAMESPACE)

.PHONY: dev_build dev_setup dev_teardown prod_build prod_setup prod_teardown
