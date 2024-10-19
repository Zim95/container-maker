# container-maker
API to create, list, delete and update containers in different container environments. Currently supported: Docker and Kubernetes

# Setup
1. Before starting this container maker you need to have grpc certificates in place.
2. To do that visit this repository: `https://github.com/Zim95/grpc_ssl_cert_generator` and follow the steps mentioned in the `README.md` file.

# Run locally
1. Clone the repository
    ```
    git clone --recurse-submodules https://github.com/Zim95/container-maker
    ```

2. Incase you miss the step to recurse submodules:
    ```
    git submodule update --init --recursive
    ```

3. Install the requirements.
    ```
    pip install -r requirements.txt
    ```

4. Run the setup command.
    ```
    pip install container-maker-spec/
    ```

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
    git clone --recurse-submodules https://github.com/Zim95/container-maker
    ```

2. Incase you miss the step to recurse submodules:
    ```
    git submodule update --init --recursive
    ```

3. Build the debug image by running this script.
    ```
    ./scripts/debug-build.sh
    ```

4. Deploy on kubernetes.
    ```
    kubectl apply -f deployement/deployment-debug.yaml
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

8. Now also run the jupyter notebook:
    ```
    pip install notebook
    ```
    Run the notebook
    ```
    jupyter notebook --allow-root
    ```
    Then from another terminal, forward port 8888.
    ```
    kubectl port-forward pod/<pod id> -n browseterm 8888:8888
    ```

# Build and deploy:
1. Clone the repository, if you haven't already.
    ```
    git clone --recurse-submodules https://github.com/Zim95/container-maker
    ```

2. Incase you miss the step to recurse submodules:
    ```
    git submodule update --init --recursive
    ```

3. Build the image