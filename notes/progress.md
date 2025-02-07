1. Finish ingress manager.
2. Check if ssh works with ingress.
3. Create a container library. - CreateContainer, GetContainer, ListContainer, DeleteContainer
    - KubernetesCreateContainer will
        - Build a pod.
        - Build a service on top of pod (based on target ports, build multiple). If required.
        - Build an ingress on top of service. If required.
    - KubernetesGetContainer will
        - Get the pod.
        - Get the service. If required.
        - Get the ingress. If required.
    - KubernetesListContainer will
        - List the pods.
        - List the services.
        - List the ingress.
    - KubernetesDeleteContainer will
        - Delete the pod.
        - Delete the service.
        - Delete the ingress.
4. Create Container Test case.
    - Create one ssh pod.
    - Create one ssh-socket pod.
    - Create an ssh pod. Only the pod. No service.
    - Create an ssh-socket ingress. Pod, Service, Ingress.
    - Create a socket client and then make a request to ssh-socket ingress.
    - Check if it works.
3. 



NOTE:
1. The number of replicas for pod should also be configurable. Our services are load balancers. So it would help in scaling.
2. Number of services will depend on the target ports of the pod. One service per target port.
3. User should be able to persist data in the pod. (Add this).


TODO:
1. Try creating a ssh container upto pod.
2. Try creating a socket ssh container all the way upto ingress.
3. Try seeing if the web socket works from outside.


Update - DO THIS NEXT TIME:
1. Building ingress is good - Build it. But it wont be needed anymore. Fix the unit test, thats the only thing remaining.
2. Build container maker - Create Container - with upto ingress, service, pod.
3. Deploy with GRPC.
4. We will use server side rendering. Meaning we wont need the socket container to be exposed to the outside world.
5. So, we will then need to build browseterm server.
   - Will render the html.
   - Will handle authentication (Google / Github).
   - Will handle User Management.
   - Will handle Container Management.


Browseterm Server:
1. Build a simple page with a container button.
2. When the container button is clicked, we will open a modal for container configuration.
3. Once, done we create a container upto service and return ip address.
4. We will then display a list to play container, delete container.
5. A side bar has 3 things.
    1. Machines section which is the terminal page.
    2. Contact section which is the contact page.
    3. About section which is the about page.
        - Tells user about the project (What you can do with it).
        - Tells user about the team. (Me).
        - Gives user the github link for contribution.
6. Once all of these work. We will put them behind an auth modal (No separate login page).


# Testing websockets
Add hello world websocket server in python. Create an image for it. Deploy it inside the cluster and test service, pods and ingress for websockets.

# TODO:
1. Add volume resource attach to pod.
2. Add service type to service.
