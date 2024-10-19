#!/bin/bash

# Image details
IMAGE_NAME=container-maker
IMAGE_TAG=latest
DOCKERFILE=Dockerfile
REPOSITORY=zim95

# docker login
docker login -u zim95

# Build image
docker image build --no-cache -t $IMAGE_NAME:$IMAGE_TAG -f $DOCKERFILE .

# Tag image
docker image tag $IMAGE_NAME:$IMAGE_TAG $REPOSITORY/$IMAGE_NAME:$IMAGE_TAG

# Push image
docker push $REPOSITORY/$IMAGE_NAME:$IMAGE_TAG
