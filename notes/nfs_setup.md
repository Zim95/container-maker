# Understanding NFS
https://www.youtube.com/watch?v=efa8gwmbPms

# Local Setup of NFS
- This setup needs to be done on the local development setup.
- The idea is, in the cloud, we get an NFS server and an NFS path.
- To mimic that, we create a local NFS on our machine and use that.
- We will not need to set this up when we move to the cloud.

# For local:
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