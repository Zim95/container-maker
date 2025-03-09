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

3. First of all, make sure `./infra/k8s/development/entrypoint-development.sh` is an executable.
    ```
    chmod +x ./infra/k8s/development/entrypoint-development.sh
    ```

4. Type the following to build the docker image for k8s development:
    ```
    ./scripts/k8s/development/k8s-development-build.sh <docker-username> <docker-repository>
    ```
    This will build the docker image required for k8s development.

    OR

    You can also edit the `Makefile`. Set values for your username and repository name.
    Then you can use the following command to build the docker image:
    ```
    make dev_build
    ```

5. Next you can setup the development environment by hitting this command:
    ```
    ./scripts/k8s/development/k8s-development-setup.sh <namespace> <absolute-path-to-current-working-directory>
    ```

    OR

    You can also edit the `Makefile`. Set values for your namespace and host directory.
    Then you can use the following command to setup the development environment:
    ```
    make dev_setup
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

12. Next setup your kubernetes cluster.

13. Also, to test things inside the pod, you can activate the virtualenv.
    ```
    source $(poetry env info --path)/bin/activate
    ```

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
