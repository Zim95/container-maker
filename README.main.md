# container-maker
API to create, list, delete and update containers in different container environments. Currently supported: Docker and Kubernetes

# Setup
1. Before starting this container maker you need to have grpc certificates in place.
2. To do that visit this repository: `https://github.com/Zim95/grpc_ssl_cert_generator` and follow the steps mentioned in the `README.md` file.
3. Next we need to clone this repository.

# Development mode
Container Maker needs to run inside a container for the libraries to work. This means, you need to develop inside a container within any of the supported environments.
Currently we support 2 environments:
### 1. Docker:

### 2. Kubernetes:
1. To Develop inside kubernetes, you need to first install Docker Desktop and follow this guideline: `https://docs.docker.com/desktop/features/kubernetes/`.
2. Once `kubectl` is setup and you have the `docker-desktop` cluster ready. We can proceed further.
3. First of all, make sure `./infra/k8s/development/entrypoint-development.sh` is an executable.
    ```
    chmod +x ./infra/k8s/development/entrypoint-development.sh
    ```
4. Type the following to build the docker image for k8s development:
    ```
    ./scripts/k8s/development/k8s-development-build.sh <docker-username> <docker-repository>
    ```
    This will build the docker image required for k8s development.
5. Next you can setup the development environment by hitting this command:
    ```
    ./scripts/k8s/development/k8s-development-setup.sh <namespace> <absolute-path-to-current-working-directory>
    ```
6. Now, that we have setup, we can check the pods with the following command:
    ```
    $ kubectl get pods -n <namespace>
    NAME                                         READY   STATUS    RESTARTS   AGE
    container-maker-development-d89777cf-h6zn2   1/1     Running   0          9s
    grpc-cert-generator-5fb88464fb-xwf8q         1/1     Running   0          9m34s
    ```
8. If the pod is running, exec into the pod:
    ```
    kubectl exec -it container-maker-development-d89777cf-h6zn2 -n <namespace> -- bash
    ```
    This will be the terminal where you run your code in.
9. Next from your local working directory, try creating a file.
    ```
    touch test1234
    ```
    This file should appear inside the pod. Type `ls` to check.
10. Once the file appears, you are good. You can make changes to your current workspace folder and then run the code from within the pod.
11. Finally, once done, you can delete everything by hitting this command:
    ```
    ./scripts/k8s/development/k8s-development-teardown.sh <namespace>
    ```
    Note: You might see some error messages on the terminal, you can ignore those.
