# Understanding NFS
https://www.youtube.com/watch?v=efa8gwmbPms

# Local Setup of NFS
- This setup needs to be done on the local development setup.
- The idea is, in the cloud, we get an NFS server and an NFS path.
- To mimic that, we create a local NFS on our machine and use that.
- We will not need to set this up when we move to the cloud.

# For local using stable nfs:
1. `helm repo add stable https://charts.helm.sh/stable`
2. `helm repo update`
3. `helm install container-maker-nfs-server stable/nfs-server-provisioner`
4. Now, an NFS server is running inside kubernetes cluster.
5. Service:
    ```
    kubectl get svc
    ```
    We should see:
    ```
    NAME                                                TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)                                                                                                     AGE
    container-maker-nfs-server-nfs-server-provisioner   ClusterIP   10.105.3.108   <none>        2049/TCP,2049/UDP,32803/TCP,32803/UDP,20048/TCP,20048/UDP,875/TCP,875/UDP,111/TCP,111/UDP,662/TCP,662/UDP   8d
    ```
6. We should be able to use NFS server:
    ```
    data.nfs_server = "container-maker-nfs-server.default.svc.cluster.local"
    data.nfs_path = "/exports"  # Or the configured export path from the chart
    ```
7. So now, we can use this NFS server in our local setup.


# Test setup
1. Everytime our test cases failed, we re-ran the test. Everytime we re-ran, the pvc would not be bound.
2. This is because, the reclaim policy was retain.
3. The persistent volume would remain even if the pvc was deleted.
4. After our tests were complete, only our pvc would be deleted. Not our pv.
5. Our pv would stay bound to an already deleted pvc and wouldn't allow another pvc to be bound to it.
6. So our pvc would stay in a pending state, and our pod would never get a pvc assigned to it.
7. So after each test, we need to manually delete the pv using:
    ```
    kubectl delete pv test-volume
    ```

# Issues:
1. First, we could not find the NFS server from the pod. Because:
    a. The service name was wrong.
        We were using:
        ```
        container-maker-nfs-server-provisioner.default.svc.cluster.local
        ```
        The actual service name was:
        ```
        container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local
        ```
        We changed that.
    b. But still we could not find the NFS server from the pod. We were getting:
        ```
        mount.nfs: Failed to resolve server container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local: Name or service not known
        ```
        Then later we got: `“Resource temporarily unavailable.”`.
    c. We tried external dns connection:
        ```
        kubectl run --rm -it temp --image=busybox -- sh -c "nslookup container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local"

        ```
    d. We also tried manual connection:
       ```
       kubectl run --rm -it temp --image=busybox -- sh -c "mkdir -p /mnt/test && mount -t nfs container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local:/exports /mnt/test && ls /mnt/test"
       ```
        We got `error: timed out waiting for the condition`.
    e. Chat suggested, that busybox image had very little lifetime and couldn't wait for the NFS server to be ready. So we tried using alpine image.
        Chat suggestions:
        The busybox image may not have the necessary NFS client utilities. Consider using an image with nfs-common (for example, an Alpine or Debian image):
        ```
        kubectl run --rm -it dns-test --image=alpine -- sh
        ```
        Then inside the shell:
        ```
        apk add --no-cache bind-tools
        nslookup container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local
        ```

        We did that and we got:
        ```
        If you don't see a command prompt, try pressing enter.
        / # nslookup container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local
        Server:		10.96.0.10
        Address:	10.96.0.10:53

        Name:	container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local
        Address: 10.105.3.108
        ```

        This meant that the connection was successful.

    f. So I asked:
        how is that the alpine image was able to resolve the DNS but not this pod?
       Answer:
        The key difference is that when you ran nslookup in an Alpine pod, the DNS resolution happened within that container using Kubernetes’ in‑cluster DNS (CoreDNS or kube-dns). However, the NFS mount operation is executed by the kubelet on the node (in your case, Docker Desktop’s underlying VM), which relies on the host’s DNS configuration.

        In other words:

        - Alpine pod (nslookup): Uses the DNS settings provided by Kubernetes to resolve service names correctly.
        - NFS mount (by kubelet): Uses the node’s resolver. On Docker Desktop, this might have a different configuration or transient issues, causing it to sometimes fail to resolve the DNS name.
        
        This discrepancy is why your Alpine pod could resolve the name, but the mount operation in your terminal pod (which is performed at the node level) is failing with NXDOMAIN and "Resource temporarily unavailable."

    So now, We thought of using the NFS ip address.

2. Using the NFS IP address:
    a. We used NFS IP address instead. When we get the svc, we get the ip address:
        ```
        kubectl get svc
        NAME                                                TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)                                                                                                     AGE
        container-maker-nfs-server-nfs-server-provisioner   ClusterIP   10.105.3.108   <none>        2049/TCP,2049/UDP,32803/TCP,32803/UDP,20048/TCP,20048/UDP,875/TCP,875/UDP,111/TCP,111/UDP,662/TCP,662/UDP   10d
        ```
        We used the ip `10.105.3.108`.
    b. We changed the value in the `development.yaml`
        ```
        - name: NFS_IP
          value: 10.105.3.108
        ```
        The value in the yaml is an environment variable. So rather than redeploying the main pod with the new yaml value,
        I simply exported the value inside the pod.
        ```
        export NFS_IP=10.105.3.108
        ```
        So now, we were good.
    c. After this, the pod was able to find the NFS. But we started getting access denied.
       ```
       Events:
        Type     Reason            Age                 From               Message
        ----     ------            ----                ----               -------
        Warning  FailedScheduling  23m                 default-scheduler  0/1 nodes are available: pod has unbound immediate PersistentVolumeClaims. preemption: 0/1 nodes are available: 1 Preemption is not helpful for scheduling.
        Normal   Scheduled         22m                 default-scheduler  Successfully assigned test-pod-manager/test-ssh-pod to docker-desktop
        Warning  FailedMount       25s (x19 over 22m)  kubelet            MountVolume.SetUp failed for volume "test-volume" : mount failed: exit status 32
        Mounting command: mount
        Mounting arguments: -t nfs 10.105.3.108:/exports /var/lib/kubelet/pods/2c998437-f149-47cd-8544-68c1f520bb94/volumes/kubernetes.io~nfs/test-volume
        Output: mount.nfs: access denied by server while mounting 10.105.3.108:/export
       ```
    d. So now we had to debug the issue by going inside the NFS pod.

3. Going inside the NFS pod to figure the issue out.
    a. First we went inside the NFS pod.
        ```
        kubectl exec -it container-maker-nfs-server-nfs-server-provisioner-0 -- bash
        ```
        We looked at the file system.
        ```
        $ ls
        bin  boot  dev	etc  export  home  lib	lib64  lost+found  media  mnt  nfs-provisioner	opt  proc  root  run  sbin  srv  sys  tmp  usr	var
        ```
    b. First i noticed that the directory was `export`, I was using `exports`. So I corrected it by overwriting the env variable.
        ```
        export NFS_PATH=/export
        ```
        earlier it was `/exports`.
        Still got ACCESS_DENIED.
    c. I did `ls -lh | grep export` and saw that the owner was `root`. I asked chat if that was the problem, only root had access, but Chat said no.
    d. When I described the `NFS` pod, I saw that it had a `default` service account, our pod was using `resource-ra` which was custom made by us. I also asked Chat if that was an issue, Chat said no.
    e. Everyone on the internet and also ChatGPT suggested that the export rules would be in etc/exports.
    f. Used `cat /etc/exports`, but got nothing back. This meant that it was empty.
    g. Chat suggested we add this line:
        ```
        /exports 192.168.65.0/24(rw,sync,no_subtree_check,no_root_squash)
        ```
        Why `192.168.65.0`?
        - ChatGPT: You might be concerned that the pod IPs (which often come from a different subnet) are not the ones that matter. However, since the mount is performed by the node (using its own IP for the request), you need to allow the node’s IP range—even if it’s in the 192.x.x.x range.
        - ChatGPT:
            Check the nodes ip address:
            ```
            kubectl describe node docker-desktop
            ```
            This gave me: `192.168.65.3`
        - ChatGpt: In your NFS server’s `/etc/exports`, you need to allow that node IP or a subnet that covers it. For example:
            ```
            /export 192.168.65.3(rw,sync,no_subtree_check,no_root_squash)
            ```
            Alternatively, if you want to allow all nodes on that network, you might use:
            ```
            /export 192.168.65.0/24(rw,sync,no_subtree_check,no_root_squash)
            ```
            For testing, allow all clients:
            ```
            /export *(rw,sync,no_subtree_check,no_root_squash)
            ```
        - Once done:
            ```
            $ exportfs -ra  # to refresh
            $ exportfs -v  # to check if the rule has been added.
            ```
    f. I had to first install `vim`. The pod had no `apt`, `yum` or anything.
        - Chat suggested i use: `cat /etc/os-release`, I sent the output to chat and i got to know the OS is Fedora.
        - The package manager is `dnf`. But `dnf` was not found.
        - Chat suggested to use `microdnf`. It worked. I used: `microdnf install -y vim`. Got `vim` installed.
        - Then I did:
            ```
            vim /etc/exports
            ```
            Added this line:
            ```
            /export *(rw,sync,no_subtree_check,no_root_squash)
            ```
            Then
            ```
            exportfs -ra
            ```
            Then
            ```
            exportfs -v
            ```
            Then reran the test, Still got ACCESS_DENIED.
    g. Then Chat suggested, I try manually mounting, NOTE: I checked the logs, the logs didn't have anything:
        ```
        kubectl run --rm -it temp --image=alpine -- sh -c "apk add --no-cache nfs-utils && mkdir -p /mnt/test && mount -t nfs 10.105.3.108:/export /mnt/test && ls /mnt/test"
        ```

        I got back:
        ```
        If you don't see a command prompt, try pressing enter.
        fetch https://dl-cdn.alpinelinux.org/alpine/v3.21/community/aarch64/APKINDEX.tar.gz
        (1/34) Installing libtirpc-conf (1.3.5-r0)
        (2/34) Installing krb5-conf (1.0-r2)
        (3/34) Installing libcom_err (1.47.1-r1)
        blah blah blah....

        mount: permission denied (are you root?)
        Session ended, resume using 'kubectl attach temp -c temp -i -t' command when the pod is running
        pod "temp" deleted
        ```
    h. Chat told me to run a priviledged pod and test:
       ```
       kubectl run --rm -it --image=alpine --overrides='
        {
        "apiVersion": "v1",
        "kind": "Pod",
        "spec": {
            "containers": [{
            "name": "temp",
            "image": "alpine",
            "securityContext": {
                "privileged": true
            },
            "command": ["sh", "-c", "apk add --no-cache nfs-utils && mkdir -p /mnt/test && mount -t nfs 10.105.3.108:/export /mnt/test && ls /mnt/test"]
            }]
        }
        }' temp
       ```
       Got this:
       ```
       error: Unable to use a TTY - container temp did not allocate one
        If you don't see a command prompt, try pressing enter.
        (1/34) Installing libtirpc-conf (1.3.5-r0)
        (2/34) Installing krb5-conf (1.0-r2)
        (3/34) Installing libcom_err (1.47.1-r1)
        (4/34) Installing keyutils-libs (1.6.3-r4)
        blah, blah, ....
        Executing busybox-1.37.0-r12.trigger
        OK: 56 MiB in 49 packages
        flock: unrecognized option: e
        BusyBox v1.37.0 (2025-01-17 18:12:01 UTC) multi-call binary.

        Usage: flock [-sxun] FD | { FILE [-c] PROG ARGS }

        [Un]lock file descriptor, or lock FILE, run PROG

            -s	Shared lock
            -x	Exclusive lock (default)
            -u	Unlock FD
            -n	Fail rather than wait
        mount.nfs: rpc.statd is not running but is required for remote locking.
        mount.nfs: Either use '-o nolock' to keep locks local, or start statd.
        mount.nfs: mounting 10.105.3.108:/export failed, reason given by server: No such file or directory
        flock: unrecognized option: e
        BusyBox v1.37.0 (2025-01-17 18:12:01 UTC) multi-call binary.

        Usage: flock [-sxun] FD | { FILE [-c] PROG ARGS }

        [Un]lock file descriptor, or lock FILE, run PROG

            -s	Shared lock
            -x	Exclusive lock (default)
            -u	Unlock FD
            -n	Fail rather than wait
        mount.nfs: rpc.statd is not running but is required for remote locking.
        mount.nfs: Either use '-o nolock' to keep locks local, or start statd.
        mount.nfs: mounting 10.105.3.108:/export failed, reason given by server: No such file or directory
        mount: mounting 10.105.3.108:/export on /mnt/test failed: Permission denied
        pod "temp" deleted
       ```
    i. Chat suggested i try the no lock option, because:
       - The message “rpc.statd is not running but is required for remote locking” means that the NFS mount process is expecting the rpc.statd daemon (which handles file locking) to be running. In minimal container images (like BusyBox), rpc.statd might not be running by default. NOTE: we are using alpine but still.

       - Also, the error says /export does not exist: `mount.nfs: mounting 10.105.3.108:/export failed, reason given by server: No such file or directory`.
         We just saw it, why is it lying to us?


       So we try the no lock option.
        ```
        kubectl run --rm -it --image=alpine --overrides='
        {
        "apiVersion": "v1",
        "kind": "Pod",
        "spec": {
            "containers": [{
            "name": "temp",
            "image": "alpine",
            "securityContext": {
                "privileged": true
            },
            "command": [
                "sh",
                "-c",
                "apk add --no-cache nfs-utils && mkdir -p /mnt/test && mount -t nfs -o nolock 10.105.3.108:/export /mnt/test && ls /mnt/test"
            ]
            }]
        }
        }' temp
        ```

        Got access denied straight up:
        ```
        Executing busybox-1.37.0-r12.trigger
        OK: 56 MiB in 49 packages
        mount.nfs: access denied by server while mounting 10.105.3.108:/export
        mount.nfs: access denied by server while mounting 10.105.3.108:/export
        mount: mounting 10.105.3.108:/export on /mnt/test failed: Permission denied
        pod "temp" deleted
        ```

        Checked for `/export` directory:
        ```
        $ ls -lh | grep export
        drwxrwxrwx   4 root root 4.0K Feb  5 18:22 export
        ```

        Oh its there! NFS pod is lying.
    
    j. Also wanted to verify if we were connecting to the correct pod, 
        ```
        kubectl run --rm -it temp --image=alpine -- sh

        apk add --no-cache nfs-utils bind-tools

        nslookup container-maker-nfs-server-nfs-server-provisioner.default.svc.cluster.local nc -zv 10.105.3.108 2049
        ```
        This showed us, the port was accepting.
        So, then the problem was with exports.

4. Problem with export rule.
    1. Chat suggested that export rule needed insecure option.
    2. We checked the export rule,
        ```
        cat /etc/exports
        /export *(rw,sync,no_subtree_check,no_root_squash,insecure)
        ```
        Insecure option is there.
    3. But our exportfs -v shows us that insecure is not part of the rule.
        ```
        exportfs -v
        /export       	<world>(sync,wdelay,hide,no_subtree_check,sec=sys,rw,no_root_squash,no_all_squash)
        ```
    4. Chat suggests we need to enable that somehow.
    5. The helm chart may have default behaviour.
    6. We will create our own values.yaml and try using that.

5. Using our own values.yaml
    Remove old one
    ```
    $ helm uninstall container-maker-nfs-server
    release "container-maker-nfs-server" uninstalled
    ```
    Now create the values.yaml. We looked at the values.yaml from github.
    Chat suggested we chanage, use ganesha to false. Since, that way we have more control over exports.
    Chat says:
        - Use ganesha decides if NFS server is run using NFS Ganesha versus the kernel NFS server.
        - We need to try usign the kernel NFS server.
        - Note: we have a new stable-nfs-values.yaml≥
    
    We will use that now:
    ```
    $ helm install container-maker-nfs-server stable/nfs-server-provisioner -f infra/k8s/development/stable-nfs-values.yaml
    
    WARNING: This chart is deprecated
    NAME: container-maker-nfs-server
    LAST DEPLOYED: Sun Feb 16 16:15:44 2025
    NAMESPACE: default
    STATUS: deployed
    REVISION: 1
    TEST SUITE: None
    NOTES:
    The NFS Provisioner service has now been installed.

    A storage class named 'nfs' has now been created
    and is available to provision dynamic volumes.

    You can use this storageclass by creating a `PersistentVolumeClaim` with the
    correct storageClassName attribute. For example:

        ---
        kind: PersistentVolumeClaim
        apiVersion: v1
        metadata:
        name: test-dynamic-volume-claim
        spec:
        storageClassName: "nfs"
        accessModes:
            - ReadWriteOnce
        resources:
            requests:
            storage: 100Mi
    ```
    
    We got this error:
    ```
    Events:
    Type     Reason     Age                From               Message
    ----     ------     ----               ----               -------
    Normal   Scheduled  88s                default-scheduler  Successfully assigned default/container-maker-nfs-server-nfs-server-provisioner-0 to docker-desktop
    Normal   Pulled     41s (x4 over 88s)  kubelet            Container image "quay.io/kubernetes_incubator/nfs-provisioner:v2.3.0" already present on machine
    Normal   Created    41s (x4 over 88s)  kubelet            Created container nfs-server-provisioner
    Normal   Started    40s (x4 over 88s)  kubelet            Started container nfs-server-provisioner
    Warning  BackOff    1s (x8 over 86s)   kubelet            Back-off restarting failed container nfs-server-provisioner in pod container-maker-nfs-server-nfs-server-provisioner-0_default(6de10094-77b4-4ae8-a241-a7eaf7013042)
    ```
    We had to check the logs and we saw the error was:
    ```
    kubectl logs container-maker-nfs-server-nfs-server-provisioner-0 -n default

    I0216 10:47:28.182367       1 main.go:64] Provisioner cluster.local/container-maker-nfs-server-nfs-server-provisioner specified
    F0216 10:47:28.184043       1 main.go:67] Invalid flags specified: if run-server is true, use-ganesha must also be true.
    ```

    So run server needs to be false as well.

6. Cannot set run server to false:
    Setting run server to false, means we need to have our own external nfs server.
    Which if we did, we wouldnt need this server at all.

    So this approach is not goint to work.


# Using local nfs server setup.
1. Setting up a local nfs server on a mac:
