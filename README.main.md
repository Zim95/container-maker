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
Container Maker needs to run inside a container for the libraries to work. This means, you need to develop inside a container within any of the supported environments.
Currently we support 2 environments:

### 1. Docker:

### 2. Kubernetes:

NOTE: This setup is a little different on windows. Please use WSL in windows.
    Basically, the script files wont work on windows and therefore, you need to manually setup.
    The developer of this repository hates working with windows.

1. To Develop inside kubernetes, you need to first install Docker Desktop and follow this guideline: `https://docs.docker.com/desktop/features/kubernetes/`.

2. Once `kubectl` is setup and you have the `docker-desktop` cluster ready. We can proceed further.

3. Clone this repository.
    ```
    git clone --recurse-submodules https://github.com/Zim95/container-maker
    ```
    In case you miss the step to recurse submodules:
    ```
    git submodule update --init --recursive
    ```

4. First of all, make sure `./infra/k8s/development/entrypoint-development.sh` is an executable.
    ```
    chmod +x ./infra/k8s/development/entrypoint-development.sh
    ```
    This is super important.

5. Create an `env.mk` file in the root of the repository and set the following variables:
    ```
    REPO_NAME=<your-docker-username>
    USER_NAME=<your-docker-username>
    NAMESPACE=<your-namespace>
    HOST_DIR=<absolute-path-to-your-local-working-directory>
    ```

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


# Setting up Kubernetes Cluster:
1. If you do not have an ingress controller installed, you can install one by following this guide: `https://kubernetes.github.io/ingress-nginx/deploy/`.
    For shortcut, you can use this command:
    ```
    helm upgrade --install ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace ingress-nginx --create-namespace
    ```
    This will install the ingress controller in the `ingress-nginx` namespace.

    Test this by checking both pods and services:
    ```
    $ kubectl get pods -n ingress-nginx
    $ kubectl get services -n ingress-nginx
    ```
    Make sure None of them are pending.

2. Setting up MetalLB for IP address allocation for external IP addresses. This is because our Service is a LoadBalancer and gets an External IP. But we dont have a cloud provider to assign an IP to the LoadBalancer. More explained below.
    ```
    # First, install MetalLB
    kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.7/config/manifests/metallb-native.yaml

    # Wait for MetalLB to be ready
    kubectl wait --namespace metallb-system \
    --for=condition=ready pod \
    --selector=app=metallb \
    --timeout=90s

    # Create an IP address pool (adjust the IP range according to your Docker network)
    cat <<EOF | kubectl apply -f -
    apiVersion: metallb.io/v1beta1
    kind: IPAddressPool
    metadata:
    name: first-pool
    namespace: metallb-system
    spec:
    addresses:
    - 172.18.255.200-172.18.255.250
    ---
    apiVersion: metallb.io/v1beta1
    kind: L2Advertisement
    metadata:
    name: l2advertisement
    namespace: metallb-system
    spec:
    ipAddressPools:
    - first-pool
    EOF
    ```

# Why use metallb?
Let me explain what was happening:
1. In a Kubernetes cluster, when you create a service of type LoadBalancer, Kubernetes expects something to provide the actual load balancer.
2. In cloud environments (like AWS, GCP, Azure), this happens automatically:
    - When you create a LoadBalancer service, the cloud provider automatically provisions a load balancer (like AWS ELB)
    - The cloud provider assigns a public IP to this load balancer
    - This IP then shows up as the EXTERNAL-IP in your service
3. In local environments (like Docker Desktop), there's no cloud provider to automatically create load balancers. This is why you saw:
    > EXTERNAL-IP: <pending>
    The ingress-nginx service was waiting for something to provide an IP address, but nothing was there to do it!
4. This is where MetalLB comes in:
    - MetalLB acts as a network load balancer for bare metal Kubernetes clusters
    - It watches for services of type LoadBalancer
    - When it finds one, it assigns an IP address from its configured pool
    - In your case, it assigned an IP from the range we configured (172.18.255.200-172.18.255.250)
5. Think of it this way:
    - Cloud Provider Load Balancer = A hotel's valet parking service
    - MetalLB = You setting up your own parking service for your house
    - Without either one, your car (service) would be waiting for someone to park it (assign an IP), hence the <pending> state!
    - This is why your ingress started working after installing MetalLB - it finally had something to provide and manage the load balancer IP addresses that your services needed.


# Why did my service get an External IP but ingress-nginx service did not?
This is because there are two different types of LoadBalancer services at play:
1. Your service's LoadBalancer:
    - This is likely using Docker Desktop's built-in load balancer capability
    - Docker Desktop can handle simple LoadBalancer services directly
    - That's why your service got an external IP

2. The ingress-nginx controller's LoadBalancer:
    - This is more complex as it needs to handle multiple services and routing rules
    - It operates at a different level (Layer 7/HTTP) compared to your service's LoadBalancer (Layer 4/TCP)
    - Docker Desktop doesn't automatically handle this more complex load balancer
    - That's why it was stuck in <pending> state until MetalLB was installed

Think of it like this:
- Your service's LoadBalancer is like a simple doorman for a single apartment
- The ingress-nginx LoadBalancer is like a complex reception desk for an entire building, handling multiple apartments and routing different visitors
- This is why:
    ```
    # Your service probably looked like this
    kubectl get svc your-service -n your-namespace
    NAME          TYPE           CLUSTER-IP       EXTERNAL-IP     PORT(S)          AGE
    your-service  LoadBalancer   10.100.200.100   192.168.65.4    80:30000/TCP     1h

    # While ingress-nginx was stuck like this
    kubectl get svc -n ingress-nginx
    NAME                       TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)           AGE
    ingress-nginx-controller   LoadBalancer   10.108.86.232   <pending>     80:31084/TCP,...  6m34s
    ```
- MetalLB was needed specifically for the more complex ingress-nginx controller's LoadBalancer service.
