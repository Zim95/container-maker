# Container Maker
Lets you manage containers across various environments. Currently supported: Kubernetes. Upcoming: Docker

How does it work?
1. Deploy the project inside one of the supported container environments.
2. Use the GRPC endpoints to create, delete or manage containers.


# Setup
1. Before starting this container maker you need to have grpc certificates in place.
2. To do that visit this repository: `https://github.com/Zim95/grpc_ssl_cert_generator` and follow the steps mentioned in the `README.md` file.
3. Next we need to clone this repository.

# Development mode
Container Maker needs to run inside a container for the libraries to work. This means, you need to develop inside a container within kubernetes.

NOTE: This setup is a little different on windows. Please use WSL in windows.
    Basically, the script files wont work on windows and therefore, you need to manually setup.
    The developer of this repository hates working with windows.

1. To Develop inside kubernetes, you need to first install Docker Desktop and follow this guideline: `https://docs.docker.com/desktop/features/kubernetes/`.

2. Once `kubectl` is setup and you have the `docker-desktop` cluster ready. We can proceed further.

3. Clone this repository.
    ```
    git clone https://github.com/Zim95/container-maker
    ```

4. First of all, make sure `./infra/k8s/development/entrypoint-development.sh` is an executable.
    ```
    chmod +x ./infra/k8s/development/entrypoint-development.sh
    ```
    This is super important.

5. Create an `env.mk` file in the root of the repository and set the following variables:
    ```
    REPO_NAME=<your-image-registry-username>
    REPO_PASSWORD=<your-image-registry-password>
    USER_NAME=<your-docker-username>
    INGRESS_HOST=<your-domain-name>
    NAMESPACE=<your-namespace>
    HOST_DIR=<absolute-path-to-your-local-working-directory>
    ```
    This is what the variables mean:
    1. REPO_NAME = Usually your docker registry name. Where you store your images.  
    2. REPO_PASSWORD = The password of your repository name.  
    3. USER_NAME = The username of your registry.  
    4. INGRESS_HOST = Your domain name. For example: example.com. You can put, localhost if you do not have a domain name yet.  
    5. NAMESPACE = The namespace of the application.  
    6. HOST_DIR = The directory where the code is located in your machine.  

6. Run the development build script, if not already done.
    ```
    make dev_build
    ```
    This will build the docker image required for k8s development.

7. Run the development setup script.
    ```
    make dev_setup
    ```
    This will setup the development environment.

8. Get inside the pod:
    First check the pod status:
    ```
    kubectl get pods -n <your-namespace>  --watch
    ```
    You should see the pod being created and then it will be running.
    ```
    NAME                                         READY   STATUS    RESTARTS   AGE
    container-maker-development-d89777cf-h6zn2   1/1     Running   0          9s
    ```
    Once the pod is running, get inside the pod:
    ```
    kubectl exec -it container-maker-development-d89777cf-h6zn2 -n <your-namespace> -- bash
    ```
    Now you are inside the pod.

9. Now we test if your local working directory is mounted to the pod.
    In your text editor outside the pod (in your local machine - working directory), create a new file and save it as `test.txt`. Check if that file is present in the pod.
    ```
    ls
    ```
    You should see the `test.txt` file.
    This means that your local working directory is mounted to the pod. You can make changes in your working directory and they will be reflected in the pod.
    You are free to develop the code and test the workings.

10. Now, we need to activate teh virtual env once we are inside the container.
    ```
    source $(poetry env info --path)/bin/activate
    ```

11. Install all dependencies with poetry.
    ```
    poetry install
    ```

12. Once done you can run the teardown script.
    ```
    make dev_teardown
    ```

NOTE: To run anything inside the shell, activate the virtualenv. But to run anything as a container command, we need to use `poetry run`.
