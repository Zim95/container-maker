# Why cant we just mount root of the container completely?
Let me explain the root mount issue first:
 - When you mount a volume at "/", it overlays the entire container filesystem. Think of it like this:
    1. Normal Container Filesystem:
        /
        ├── bin/      (system binaries)
        ├── etc/      (configuration)
        ├── lib/      (system libraries)
        ├── usr/      (user programs)
        ├── proc/     (process info)
        ├── sys/      (kernel interface)
        ├── dev/      (devices)
        └── app/      (your application)
    2. When mounting an empty volume at "/":
        /
        └── (empty)   (all original files are hidden)
 - The volume "masks" everything because Linux mounts work as overlays. If the volume is empty, you can't see what's underneath.


# How do we solve this?
1. We first mount all of our required directories except system directories and create a .initialized file.
   ```
   "sh",
    "-c",
    """
    if [ ! -f /persist/.initialized ]; then
        echo "Initializing persistent volume..."
        # Copy everything except special filesystems
        cd / && \
        tar cf - \
            --exclude=/proc \
            --exclude=/sys \
            --exclude=/dev \
            --exclude=/persist \
            . | (cd /persist && tar xf -)
        touch /persist/.initialized
        echo "Filesystem initialized."
    else
        echo "Filesystem already initialized."
    fi
    """
   ```
   We do this in init container.
   Notice, that the next time the pod is started, the init container will not mount the same directories again, as it checks for the .initialized file.

   Why is this important?
   - Imagine, when the pod crashes, you write down all changes you have to the volume.
   - It starts again, and just copies the freshly created pod's files into the volume.
   - This way, you lose all the changes you made to the volume.
   - So, we need to make sure that the init container only runs once. When the pod is originally created and the volume is empty.
   - Once the volume is initialized, the init container will not run again.

2.  Next, we create a volume mount in the /persist directory. This is where the init container will copy the files. We will need to make sure that the pod is able to write to this directory. Therefore, we need to mount the volume at /persist.

3. Next, we set the mount_propagation to hostToContainer. This is important because we want the pod to be able to write to the volume.
   Any changes made to the pod needs to be written to volume.

   mount_propagation -> Controls how mounts are shared between host and container.
   Options are:
    - None: Default, mounts are private
    - HostToContainer: Container sees new mounts from host
    - Bidirectional: Both host and container see new mounts
   We use HostToContainer to ensure container sees all system mounts.

   NOTE:
   ----
   In Kubernetes:
    Host:
     - The physical/virtual machine running the Kubernetes node
     - The actual server where your pods run
     - Has its own filesystem, processes, and resources
     - Can run multiple containers
    Container:
     - Your application running in an isolated environment
     - Has its own view of filesystem, processes, and resources
     - Runs on the host
     - Is more restricted than the host
   So when we say HostToContainer:
     - Changes in host's mounts are visible to container
     - Example: If host mounts a new disk at /data, container can see it
     - But container's mounts aren't visible to host
     - It's a one-way propagation: Host → Container
   Think of it like:
        Host Machine
        ├── System Files
        ├── Kubernetes
        └── Your Pod
            └── Your Container (can see host mounts)
   This is important for security:
     - Container can't affect host's filesystem
     - But can see necessary system mounts from host
     - Maintains isolation while allowing required access

4. We then use subPath='.'.
    - Without subPath: Entire volume replaces directory contents
    - With subPath: Only mounts specific directory from volume
    - "." means "current directory" - mounts volume content without masking
    - Helps prevent masking of system directories like /proc, /sys, /dev

5. Sync on Shutdown:
    ```
    "preStop": {
       "exec": {
           "command": ["sh", "-c", "sync"]
        }
    }
    ```
    - Forces all pending writes to disk
    - Prevents data loss during shutdown
    - Like "safely remove USB drive" on your computer
    - Here's a visual of what happens:
        ```
        First Start:
        1. Empty Volume (/persist)  →  Init Container copies files  →  Main Container uses files
        []                          [container files copied]        [running with persisted files]

        Subsequent Starts:
        2. Filled Volume (/persist)  →  Init Container skips copy  →  Main Container uses existing files
        [previous files]             [.initialized exists]         [running with previous files]
        ```



# Why use persistence if host path is still available?
Yes, your current implementation with PV/PVC and the init container setup is still the right approach because:

1. You want full filesystem persistence:
```python
# Your current setup:
init_containers=[  # Copies entire filesystem
    V1Container(
        command=["sh", "-c", "if [ ! -f /persist/.initialized ]; then cp -a /. /persist/..."]
    )
],
containers=[
    V1Container(
        volume_mounts=[
            V1VolumeMount(
                mount_path="/",  # Mounts at root for full filesystem access
                mount_propagation="HostToContainer"
            )
        ]
    )
]
```

This gives you:
- Complete filesystem persistence
- All installations/changes saved
- Works across node restarts/moves
- Proper data management

2. Simple hostPath wouldn't give you:
- Full filesystem persistence
- Node independence
- Data management features
- Production readiness

So yes, for your use case (persisting the entire container state), the current implementation with:
1. PV/PVC
2. Init container
3. Root mount
4. Sync on shutdown

Is the correct approach, even though it's more complex than a simple hostPath.

My question:
ohh right since host is a node,. if node changes those changes are gone.

But since we are persisting in the volume. That should be fine for us


Exactly! You've got it. Here's why your PV/PVC approach is better:
```
Simple hostPath:
Pod ←→ Node1:/tmp/data
      If pod moves to Node2, data is lost!

Your PV/PVC setup:
Pod ←→ PV/PVC ←→ Storage
      Pod can move to any node
      Data follows the pod!
```

Your implementation:
- Uses PV/PVC which is node-independent
- Properly initializes the filesystem with init container
- Persists all changes via root mount
- Syncs data before shutdown
- Works even if:
    - Pod moves to different node
    - Node crashes
    - Cluster scales up/down
    - Pod gets rescheduled

This is why we went with the more complex but robust solution instead of just using hostPath. The data persistence is truly portable and production-ready!


Here is the final pod manifest:
```python
# create pod manifest
            pod_manifest: V1Pod = V1Pod(
                metadata=V1ObjectMeta(
                    name=data.pod_name,
                    labels={"app": data.pod_name},
                    annotations={
                        "nginx.org/websocket-services": data.pod_name,  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600"  # for websockets
                    }
                ),
                spec=V1PodSpec(
                    # Init container to prepare the filesystem
                    init_containers=[
                        V1Container(
                            name=f"{data.pod_name}-init",
                            image=data.image_name,
                            command=[
                                "sh",
                                "-c",
                                """
                                if [ ! -f /persist/.initialized ]; then
                                    echo "Initializing persistent volume..."
                                    # Copy everything except special filesystems
                                    cd / && \
                                    tar cf - \
                                        --exclude=/proc \
                                        --exclude=/sys \
                                        --exclude=/dev \
                                        --exclude=/persist \
                                        . | (cd /persist && tar xf -)
                                    touch /persist/.initialized
                                    echo "Filesystem initialized."
                                else
                                    echo "Filesystem already initialized."
                                fi
                                """
                            ],
                            volume_mounts=[
                                V1VolumeMount(
                                    name=data.volume_config['volume']['volume_name'],
                                    mount_path="/persist"
                                )
                            ]
                        )
                    ] if data.volume_config else None,
                    
                    # Main container
                    containers=[
                        V1Container(
                            name=data.pod_name,
                            image=data.image_name,
                            ports=target_ports,
                            env=environment_variables,
                            volume_mounts=[
                                V1VolumeMount(
                                    name=data.volume_config['volume']['volume_name'],
                                    mount_path="/",
                                    mount_propagation="HostToContainer",
                                    # Exclude system paths
                                    sub_path=".",
                                )
                            ] if data.volume_config else None,
                            # Add lifecycle hook to sync filesystem before shutdown
                            lifecycle={
                                "preStop": {
                                    "exec": {
                                        "command": [
                                            "sh",
                                            "-c",
                                            "sync"  # Ensure all writes are flushed
                                        ]
                                    }
                                }
                            }
                        )
                    ],
                    volumes=[
                        V1Volume(
                            name=data.volume_config['volume']['volume_name'],
                            persistent_volume_claim=V1PersistentVolumeClaimVolumeSource(
                                claim_name=data.volume_config['claim']['claim_name']
                            )
                        )
                    ] if data.volume_config else None
                )
            )
```


NOTE:
1. The above approach wont work on a multi node scneario because no matter the init container setup, the volume is also mounted on a node.
2. So when moving to a new node, the volume is not available.
3. Because with hostPath, the volume is tied to a specific filesytem on a node and is not a multi node volume.
4. So even if we did persist in the volume, that shit wont work, because the volume itself is not available on a different node.


# NFS
1. So now, we need to use NFS.
2. NFS is shared across Nodes.
3. So persisting there is a better choice.

# Articles on NFS
1. [Setup Dynamic NFS Provisioning](https://hbayraktar.medium.com/how-to-setup-dynamic-nfs-provisioning-in-a-kubernetes-cluster-cbf433b7de29)

