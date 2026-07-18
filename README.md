# container-maker
API to create, list, delete and update containers in different container environments. Currently supported: Docker and Kubernetes

# Setup
1. Before starting this container maker you need to have grpc certificates in place.
2. To do that visit this repository: `https://github.com/Zim95/grpc_ssl_cert_generator` and follow the steps mentioned in the `README.md` file.

# Run locally
1. Clone the repository.
    ```
    git clone https://github.com/Zim95/container-maker
    ```

2. Create the virtual environment and install dependencies with Poetry.  
    Make sure that python3.11 is installed in your system.
    ```
    poetry install --no-root
    ```

4. `container-maker-spec` is declared as a Poetry git dependency in `pyproject.toml`, so it is installed automatically by the previous step. There is no local `container-maker-spec/` directory to install.

5. You should now be able to run the application.
    ```
    python app.py
    ```

6. If you want to run in ssl mode, you need the certificates locally. You can go to this: `https://github.com/Zim95/grpc_ssl_cert_generator` repository and look up how to generate only certificates. Once done, you can use the following command:
    ```
    python app.py --use_ssl true
    ```

# Build and deploy: Debug
1. Clone the repository, if you haven't already.
    ```
    git clone https://github.com/Zim95/container-maker
    ```

2. There are no git submodules here; `container-maker-spec` is pulled in automatically as a Poetry git dependency.

3. Build the development image.
    ```
    make dev_build
    ```

4. Deploy on kubernetes. `make dev_setup` envsubst's `infra/k8s/development/development.yaml` and applies it.
    ```
    make dev_setup
    ```

5. Check for the pods:
    ```
    kubectl get pods -n browseterm | grep container-maker-debug
    ```

6. Exec into any one of the pods (if there are multiple):
    ```
    kubectl exec -it <pod id> -n browseterm -- bash
    ```

7. Either run `ipython` to check for changes. Or you can run the app:
    ```
    python app.py --use_ssl true
    ```

8. Now also run the jupyter notebook. Do this from a separate terminal window, keep the app running:
    ```
    kubectl port-forward pod/<pod id> -n browseterm 8888:8888
    ```
    Navigate to `localhost:8000` and go to the `demo` folder.

9. You can now make changes and experment things using the jupyter notebook.

# Build and deploy:
1. Clone the repository, if you haven't already.
    ```
    git clone https://github.com/Zim95/container-maker
    ```

2. There are no git submodules here; `container-maker-spec` is pulled in automatically as a Poetry git dependency.

3. Build the image

> **Note:** The `prod_*` make targets are currently WIP — they reference missing `scripts/k8s/deployment/*.sh` scripts. Also note that cert-manager must mint the `container-maker-development-service-certs` secret before this pod becomes healthy.