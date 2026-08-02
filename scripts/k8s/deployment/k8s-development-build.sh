#!/bin/bash
# Build + push the container-maker PRODUCTION image. Usage: $0 <docker-username> <docker-repository>
if [ $# -lt 2 ]; then echo "Usage: $0 <docker-username> <docker-repository>"; exit 1; fi
USERNAME=$1
REPOSITORY=$2
IMAGE_NAME=container-maker
IMAGE_TAG=latest
DOCKERFILE=./infra/k8s/deployment/Dockerfile.deployment
docker login -u "$USERNAME"
docker image build -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKERFILE .
docker image tag $IMAGE_NAME:$IMAGE_TAG $REPOSITORY/$IMAGE_NAME:$IMAGE_TAG
docker push $REPOSITORY/$IMAGE_NAME:$IMAGE_TAG
