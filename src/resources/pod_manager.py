# modules
from abc import ABC, abstractmethod
import base64
import time
import os
from datetime import datetime
import gc  # this is because we use the stream function which does not close sockets properly. So we manually collect them using gc.
import warnings  # this is to capture resource warnings.
from typing import List
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.get_pod_dataclass import GetPodDataClass
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass, ResourceRequirementsDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.resources.resource_config import POD_IP_TIMEOUT_SECONDS, POD_UPTIME_TIMEOUT, POD_TERMINATION_TIMEOUT, STATUS_SIDECAR_IMAGE_NAME, STATUS_SIDECAR_NAME, CONTAINER_READINESS_TIMEOUT_SECONDS, IMAGE_BUILD_TIMEOUT_MINUTES
from src.resources.resource_config import SNAPSHOT_DIR, SNAPSHOT_FILE_NAME
from src.common.config import REPO_NAME, REPO_PASSWORD
from browseterm_storage import StorageLayer, get_storage

# third party
from kubernetes.client.rest import ApiException
from kubernetes.client import V1EnvVar
from kubernetes.client import V1ContainerPort
from kubernetes.client import V1Pod
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1PodSpec
from kubernetes.client import V1Container
from kubernetes.client import V1SecurityContext
from kubernetes.client import V1Volume
from kubernetes.client import V1EmptyDirVolumeSource
from kubernetes.client import V1VolumeMount
from kubernetes.client import V1ResourceRequirements
from kubernetes.client import V1ServiceAccount
from kubernetes.client import RbacAuthorizationV1Api
from kubernetes.client import V1Role
from kubernetes.client import V1RoleBinding
from kubernetes.client import V1PolicyRule
from kubernetes.client import V1RoleRef
from kubernetes.client import RbacV1Subject
from kubernetes.stream import ws_client
from kubernetes.stream import stream

# Constants for RBAC
STATUS_SIDECAR_SERVICE_ACCOUNT_NAME = 'status-sidecar-sa'
STATUS_SIDECAR_ROLE_NAME = 'pod-watcher-role'
STATUS_SIDECAR_ROLE_BINDING_NAME = 'pod-watcher-binding'


class ExecUtility(KubernetesResourceManager):
    '''
    Utility class for executing commands in a pod.
    '''

    @classmethod
    def run_command(cls, pod_name: str, namespace_name: str, container_name: str, command: str) -> str:
        '''
        Exec a command into a pod container and return the output
        :params: pod_name: str - Name of the pod
        :params: namespace_name: str - Name of the namespace  
        :params: container_name: str - Name of the container within the pod
        :params: command: str - Command to execute
        :returns: str - Command output
        '''
        try:
            cls.check_kubernetes_client()

            # Temporarily suppress the specific ResourceWarning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*ssl.SSLSocket.*")
                # For simple output, use preload_content=True
                output: str = stream(
                    cls.client.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace_name,
                    container=container_name,
                    command=["/bin/bash", "-c", command],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=True
                )
                # Force garbage collection to clean up any lingering connections
                gc.collect()
            return output.strip() if output else "" 
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while executing command in pod: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Unknown error occured: {str(e)}') from e

    @classmethod
    def run_command_with_stream(cls, pod_name: str, namespace_name: str, container_name: str, command: str, timeout_minutes: int = IMAGE_BUILD_TIMEOUT_MINUTES) -> str:
        '''
        Exec a command into a pod container with real-time streaming output.
        :params: pod_name: str - Name of the pod
        :params: namespace_name: str - Name of the namespace  
        :params: container_name: str - Name of the container within the pod
        :params: command: str - Command to execute
        :params: timeout_minutes: int - Maximum time to wait for command completion
        :returns: str - Complete command output
        '''
        try:
            cls.check_kubernetes_client()
            # Suppress ResourceWarning for streaming connections
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*ssl.SSLSocket.*")
                # Create WebSocket connection with _preload_content=False for streaming
                stream_client: ws_client.WSClient = stream(
                    cls.client.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace_name,
                    container=container_name,
                    command=["/bin/bash", "-c", command],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=False  # This gives us a WebSocket client for streaming
                )
                try:
                    output: str = ""
                    start_time: float = time.time()
                    timeout_seconds: float = timeout_minutes * 60
                    while stream_client.is_open():
                        # Check for timeout
                        if time.time() - start_time > timeout_seconds:
                            raise TimeoutError(f"Command timed out after {timeout_minutes} minutes")
                        stream_client.update(timeout=5)
                        if stream_client.peek_stdout():
                            stdout_chunk: str = stream_client.read_stdout()
                            output += stdout_chunk
                            if stdout_chunk.strip():
                                print(f"[{container_name}] {stdout_chunk.strip()}")
                        if stream_client.peek_stderr():
                            stderr_chunk: str = stream_client.read_stderr()
                            output += stderr_chunk
                            if stderr_chunk.strip():
                                print(f"[{container_name}] {stderr_chunk.strip()}")
                    return output.strip()
                finally:
                    # Always close the stream client
                    try:
                        stream_client.close()
                    except Exception:
                        pass
                    # Force garbage collection to clean up any lingering connections
                    gc.collect()
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while executing command in pod: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Unknown error occured: {str(e)}') from e

    @classmethod
    def stream_command_to_file(cls, pod_name: str, namespace_name: str, container_name: str, command: str, local_path: str, timeout_minutes: int = IMAGE_BUILD_TIMEOUT_MINUTES) -> int:
        '''
        Exec a command whose stdout is base64 text (e.g. `base64 -w 0 <file>`), decode it
        incrementally and write the raw bytes to local_path. Memory stays bounded (only a small
        base64 carry buffer is held at a time) so we can pull a large filesystem snapshot out of
        a pod without buffering the whole thing in RAM (which OOM-killed container-maker before).
        :params: pod_name: str - Name of the pod
        :params: namespace_name: str - Name of the namespace
        :params: container_name: str - Name of the container within the pod
        :params: command: str - Command to execute (its stdout must be base64)
        :params: local_path: str - Local file to write the decoded bytes to
        :params: timeout_minutes: int - Maximum time to wait for command completion
        :returns: int - number of bytes written to local_path
        '''
        try:
            cls.check_kubernetes_client()
            bytes_written: int = 0
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*ssl.SSLSocket.*")
                stream_client: ws_client.WSClient = stream(
                    cls.client.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace_name,
                    container=container_name,
                    command=["/bin/bash", "-c", command],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=False
                )
                try:
                    start_time: float = time.time()
                    timeout_seconds: float = timeout_minutes * 60
                    b64_carry: str = ""      # leftover base64 chars; only decode on 4-char boundaries
                    stderr_output: str = ""
                    with open(local_path, "wb") as f:
                        while stream_client.is_open():
                            if time.time() - start_time > timeout_seconds:
                                raise TimeoutError(f"Command timed out after {timeout_minutes} minutes")
                            stream_client.update(timeout=5)
                            if stream_client.peek_stdout():
                                # strip all whitespace so the 4-char boundary math stays correct
                                b64_carry += "".join(stream_client.read_stdout().split())
                                n: int = (len(b64_carry) // 4) * 4
                                if n:
                                    chunk, b64_carry = b64_carry[:n], b64_carry[n:]
                                    decoded: bytes = base64.b64decode(chunk)
                                    f.write(decoded)
                                    bytes_written += len(decoded)
                            if stream_client.peek_stderr():
                                stderr_output += stream_client.read_stderr()
                        # flush any remaining base64 (a valid stream ends on a 4-char boundary)
                        if b64_carry:
                            decoded = base64.b64decode(b64_carry)
                            f.write(decoded)
                            bytes_written += len(decoded)
                    if stderr_output.strip():
                        print(f"[{container_name}] {stderr_output.strip()}")
                    return bytes_written
                finally:
                    try:
                        stream_client.close()
                    except Exception:
                        pass
                    gc.collect()
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while streaming command output in pod: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Unknown error occured: {str(e)}') from e


class StorageUtility(ABC):
    '''
    Abstract base class for storage utilities.
    Handles tar creation and storage based on the storage layer.
    '''

    @abstractmethod
    def build_tar(self, data: SavePodDataClass) -> str:
        '''
        Build and store tar file based on storage backend.
        :params: data: SavePodDataClass
        :returns: str: Snapshot path (local path or storage key)
        '''
        pass

    @classmethod
    @abstractmethod
    def get_storage_envs(cls) -> dict:
        '''
        Get storage-specific environment variables for the snapshot job.
        :returns: dict: Environment variables for storage configuration
        '''
        pass


class LocalPVCStorageUtility(StorageUtility):
    '''
    Utility for local PVC storage.
    Creates tar file directly on shared PVC volume.
    '''

    @classmethod
    def get_storage_envs(cls) -> dict:
        '''
        Get storage-specific environment variables for local PVC storage.
        :returns: dict: Environment variables with STORAGE_LAYER and SNAPSHOT_DIR
        '''
        return {
            "STORAGE_LAYER": "local",
            "SNAPSHOT_DIR": SNAPSHOT_DIR,
        }

    @classmethod
    def build_tar(cls, data: SavePodDataClass) -> str:
        '''
        Build a tar file of the main container's filesystem on local PVC.
        :params: data: SavePodDataClass
        :returns: str: Local snapshot path
        '''
        try:
            KubernetesResourceManager.check_kubernetes_client()
            
            # Generate timestamp for snapshot
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            
            # Get storage instance for LOCAL
            local_storage_config = {'snapshot_dir': SNAPSHOT_DIR}
            storage = get_storage(StorageLayer.LOCAL, local_storage_config)
            
            # Get snapshot path from storage
            snapshot_path = storage.snapshot_path(data.namespace_name, data.pod_name, timestamp)
            
            # Build the tar file
            tar_cmd: str = (
                f"mkdir -p {os.path.dirname(snapshot_path)} && "
                f"tar --exclude=/proc --exclude=/sys --exclude=/dev --exclude={SNAPSHOT_DIR} "
                f"-czvf {snapshot_path} /"
            )
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.pod_name, tar_cmd)
            print(f"{data.pod_name}: Filesystem snapshot created in main container at {snapshot_path}.")
            return snapshot_path
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error creating local snapshot: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Error creating local snapshot: {str(e)}') from e


class MinioStorageUtility(StorageUtility):
    '''
    Utility for MinIO storage.
    Creates tar file in pod, reads it, and uploads to MinIO.
    '''

    @classmethod
    def get_storage_envs(cls) -> dict:
        '''
        Get storage-specific environment variables for MinIO storage.
        :returns: dict: Environment variables with STORAGE_LAYER, MinIO credentials, and SNAPSHOT_DIR
        '''
        return {
            "STORAGE_LAYER": "minio",
            "SNAPSHOT_DIR": SNAPSHOT_DIR,
            "MINIO_ENDPOINT": os.getenv('MINIO_ENDPOINT'),
            "MINIO_ACCESS_KEY": os.getenv('MINIO_ACCESS_KEY'),
            "MINIO_SECRET_KEY": os.getenv('MINIO_SECRET_KEY'),
            "MINIO_BUCKET": os.getenv('MINIO_BUCKET'),
            "MINIO_SECURE": os.getenv('MINIO_SECURE', 'false'),
        }

    @classmethod
    def build_tar(cls, data: SavePodDataClass) -> str:
        '''
        Build a tar file of the main container's filesystem and upload to MinIO.
        :params: data: SavePodDataClass
        :returns: str: MinIO object key
        '''
        try:
            KubernetesResourceManager.check_kubernetes_client()
            
            # Generate timestamp for snapshot
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            
            # Get storage instance for MINIO
            minio_storage_config = {
                'minio_endpoint': os.getenv('MINIO_ENDPOINT'),
                'minio_access_key': os.getenv('MINIO_ACCESS_KEY'),
                'minio_secret_key': os.getenv('MINIO_SECRET_KEY'),
                'minio_bucket': os.getenv('MINIO_BUCKET'),
                'minio_secure': os.getenv('MINIO_SECURE', 'false').lower() == 'true',
            }
            storage = get_storage(StorageLayer.MINIO, minio_storage_config)
            
            # Get snapshot path from storage
            snapshot_path = storage.snapshot_path(data.namespace_name, data.pod_name, timestamp)
            
            # Create temp local path for tar creation in pod
            temp_tar_path = f"{SNAPSHOT_DIR}/{data.namespace_name}/{data.pod_name}/fs_snapshot_{timestamp}.tar.gz"
            
            # Build the tar file inside pod
            tar_cmd: str = (
                f"mkdir -p {os.path.dirname(temp_tar_path)} && "
                f"tar --exclude=/proc --exclude=/sys --exclude=/dev --exclude={SNAPSHOT_DIR} "
                f"-czvf {temp_tar_path} /"
            )
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.pod_name, tar_cmd)
            print(f"{data.pod_name}: Filesystem snapshot created in main container.")

            # Stream the tar out of the pod to a local temp file (base64 over exec, decoded
            # incrementally) so we never hold the whole filesystem in memory, then upload the
            # file to MinIO with fput_object (multipart, streams from disk). This avoids the OOM
            # that reading the entire base64 tar into a Python str caused before.
            local_tmp: str = f"/tmp/{data.namespace_name}_{data.pod_name}_{timestamp}.tar.gz"
            try:
                b64_cmd: str = f"base64 -w 0 {temp_tar_path}"
                ExecUtility.stream_command_to_file(data.pod_name, data.namespace_name, data.pod_name, b64_cmd, local_tmp)
                # fput_object streams from disk in parts (no full in-memory load, unlike write()).
                storage.client.fput_object(storage.bucket, snapshot_path, local_tmp)
                print(f"{data.pod_name}: Snapshot uploaded to MinIO at {snapshot_path}.")
            finally:
                if os.path.exists(local_tmp):
                    os.remove(local_tmp)
                # best-effort cleanup of the in-pod tar so repeated saves don't fill the pod
                try:
                    ExecUtility.run_command(data.pod_name, data.namespace_name, data.pod_name, f"rm -f {temp_tar_path}")
                except Exception:
                    pass
            return snapshot_path
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error creating MinIO snapshot: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Error creating MinIO snapshot: {str(e)}') from e


class SaveUtility(KubernetesResourceManager):
    '''
    Utility class for saving a pod.
    This class assumes that all containers and pods are available.
    This is because we cannot use PodManager because PodManager uses this utility.
    That is a cyclic dependency.

    Therefore, make sure the main container is available before calling this utility.
    '''

    @classmethod
    def build_tar(cls, data: SavePodDataClass) -> str:
        '''
        Build a tar file of the main container's filesystem using appropriate storage utility.
        :params: data: SavePodDataClass
        :returns: str: Snapshot path (local path or storage key)
        '''
        try:
            cls.check_kubernetes_client()

            # Get storage layer from environment
            storage_layer_str = os.getenv('STORAGE_LAYER', 'local').lower()
            storage_layer = StorageLayer(storage_layer_str)
            storage_utility_map = {
                StorageLayer.LOCAL: LocalPVCStorageUtility,
                StorageLayer.MINIO: MinioStorageUtility
            }
            storage_utility: StorageUtility = storage_utility_map.get(storage_layer)
            if storage_utility is None:
                raise ValueError(f'Unsupported STORAGE_LAYER: {storage_layer}')
            return storage_utility.build_tar(data)
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating snapshot: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occured while creating snapshot: {str(e)}') from e

    @classmethod
    def save_image(cls, data: SavePodDataClass) -> dict:
        '''
        Save the pod by creating a Kubernetes Job to build and push the snapshot.
        
        :params:
            data: SavePodDataClass with environment_variables containing container_id and db credentials
        :returns: dict: Job information
        '''
        try:
            cls.check_kubernetes_client()
            from src.resources.job_manager import JobManager
            
            repo_name: str = REPO_NAME
            repo_password: str = REPO_PASSWORD
            if not repo_name or not repo_password:
                raise Exception('REPO_NAME or REPO_PASSWORD is not set')
            
            # Step 1: Main container creates the tar file
            print(f"{data.pod_name}: Creating filesystem snapshot...")
            snapshot_path = cls.build_tar(data)
            
            # Step 2: Create a Kubernetes Job to process the snapshot
            print(f"{data.pod_name}: Creating snapshot job...")
            env_vars = data.environment_variables or {}

            # Extract required values from environment_variables
            container_id = env_vars.get("CONTAINER_ID")
            db_host = env_vars.get("DB_HOST")
            db_port = int(env_vars.get("DB_PORT", 5432))
            db_username = env_vars.get("DB_USERNAME")
            db_password = env_vars.get("DB_PASSWORD")
            db_database = env_vars.get("DB_DATABASE")

            # Get storage-specific environment variables from the utility
            storage_layer_str = os.getenv('STORAGE_LAYER', 'local').lower()
            storage_layer = StorageLayer(storage_layer_str)
            storage_utility_map = {
                StorageLayer.LOCAL: LocalPVCStorageUtility,
                StorageLayer.MINIO: MinioStorageUtility
            }
            storage_utility = storage_utility_map.get(storage_layer)
            storage_env_vars = storage_utility.get_storage_envs() if storage_utility else {}

            job_info = JobManager.create_snapshot_job(
                namespace_name=data.namespace_name,
                pod_name=data.pod_name,
                container_id=container_id,
                repo_name=repo_name,
                repo_password=repo_password,
                db_host=db_host,
                db_port=db_port,
                db_username=db_username,
                db_password=db_password,
                db_database=db_database,
                snapshot_path=snapshot_path,
                storage_env_vars=storage_env_vars
            )
            
            # Step 3: Wait for job to complete
            print(f"{data.pod_name}: Waiting for snapshot job to complete...")
            JobManager.wait_for_job_completion(
                namespace_name=job_info['namespace_name'],
                job_name=job_info['job_name']
            )
            # Job updates the database directly, so we just return the image name.
            # NOTE: must match what the snapshot Job actually pushed (and wrote to saved_image):
            # {REPO_NAME}/{pod_name}-image:latest. Without the repo prefix the kubelet can't pull it
            # (ImagePullBackOff), which previously broke the live terminal on every save.
            image_name = f'{repo_name}/{data.pod_name}-image:latest'
            print(f"{data.pod_name}: Snapshot job completed successfully")

            # Step 4: Point the pod's main container at the saved image, so if it CRASHES the kubelet
            # restarts it from the snapshot immediately (in-place crash recovery). Deliberate
            # hibernation deletes the pod entirely and resumes via create-from-saved_image instead.
            print(f"{data.pod_name}: Updating pod image definition to {image_name}...")
            PodManager._update_pod_image(
                namespace_name=data.namespace_name,
                pod_name=data.pod_name,
                image_name=image_name
            )
            print(f"{data.pod_name}: Pod image definition updated (used for in-place crash recovery)")
            
            return {
                'image_name': image_name
            }
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while saving pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Save pod error occured: {str(e)}') from e


class PodManager(KubernetesResourceManager):
    '''
    Manage kubernetes pods.
    '''

    @classmethod
    def get_container_ports(cls, container: V1Container) -> list[dict]:
        """
        Get ports of a single container as a list of dictionaries.

        Args:
            container: V1Container object.

        Returns:
            List of ports with name, container_port, and protocol.
        """
        ports: list[dict] = []
        if container.ports:
            for port in container.ports:
                ports.append({
                    'name': port.name if port.name else None,
                    'container_port': port.container_port,
                    'protocol': port.protocol
                })
        return ports

    @classmethod
    def get_pod_ports(cls, pod: V1Pod) -> list[dict]:
        """
        Get all ports configured for a pod's containers.
        :params: pod: V1Pod
        :returns: list[dict]: List of ports
        """
        ports: list[dict] = []
        for container in pod.spec.containers:
            if container.ports:
                for port in container.ports:
                    ports.append({
                        'name': port.name if port.name else None,
                        'container_port': port.container_port,
                        'protocol': port.protocol
                    })
        return ports

    @classmethod
    def get_pod_containers(cls, pod: V1Pod) -> list[dict]:
        """
        Get all containers for a pod.
        :params: pod: V1Pod
        :returns: list[dict]: List of containers
        """
        if not pod.spec.containers:
            return []

        containers: list[dict] = []

        # snapshot_size_limit is a property of the EmptyDir volume, not a
        # Kubernetes compute resource. Derive it once from the pod's volumes
        # (e.g. the "snapshot-volume" EmptyDir.size_limit) and then attach it
        # to each container's resource view for convenience.
        snapshot_size_limit: str | None = None
        if pod.spec.volumes:
            for volume in pod.spec.volumes:
                empty_dir: V1EmptyDirVolumeSource | None = getattr(volume, "empty_dir", None)
                if empty_dir is not None and getattr(empty_dir, "size_limit", None):
                    # If multiple volumes exist, we take the first one that has a size_limit.
                    snapshot_size_limit = empty_dir.size_limit
                    break

        for container in pod.spec.containers:
            # Derive per-container compute resources from the Kubernetes spec
            resources: V1ResourceRequirements = container.resources or V1ResourceRequirements()
            requests: dict | None = getattr(resources, "requests", None)
            limits: dict | None = getattr(resources, "limits", None)
            container_resources: dict = {
                'cpu_request': (requests or {}).get('cpu'),
                'cpu_limit': (limits or {}).get('cpu'),
                'memory_request': (requests or {}).get('memory'),
                'memory_limit': (limits or {}).get('memory'),
                'ephemeral_request': (requests or {}).get('ephemeral-storage'),
                'ephemeral_limit': (limits or {}).get('ephemeral-storage'),
                # Not a native container resource; exposed here as a convenience
                # and derived from the pod's EmptyDir volume.
                'snapshot_size_limit': snapshot_size_limit,
            }

            containers.append(
                {
                    'resource_type': 'pod_container',
                    'container_name': container.name,
                    'container_image': container.image,
                    'container_ports': cls.get_container_ports(container),
                    'container_resources': container_resources,
                }
            )
        return containers

    @classmethod
    def get_pod_response(cls, pod: V1Pod) -> dict:
        '''
        Get the pod response.
        :params: pod: V1Pod
        :returns: dict: Pod Details
        '''
        return {
            'resource_type': 'pod',
            'pod_id': pod.metadata.uid,
            'pod_name': pod.metadata.name,
            'pod_namespace': pod.metadata.namespace,
            'pod_ip': cls.get_pod_ip(pod.metadata.namespace, pod.metadata.name),
            'pod_ports': cls.get_pod_ports(pod),
            'pod_labels': pod.metadata.labels or {},
            'associated_resources': cls.get_pod_containers(pod),
        }

    @classmethod
    def list(cls, data: ListPodDataClass) -> list[dict]:
        '''
        List all pods in a namespace.
        :params: data: ListPodDataClass
        :returns: list[dict]: List of pods
        '''
        try:
            cls.check_kubernetes_client()
            return [
                cls.get_pod_response(pod)
                for pod in cls.client.list_namespaced_pod(namespace=data.namespace_name).items
            ]
        except ApiException as ae:
            raise ApiException(f'Error occurred while listing pods: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get(cls, data: GetPodDataClass) -> dict:
        '''
        Get a pod.
        :params: data: GetPodDataClass
        :returns: dict: Pod Details
        '''
        try:
            cls.check_kubernetes_client()
            response: V1Pod = cls.client.read_namespaced_pod(name=data.pod_name, namespace=data.namespace_name)
            return cls.get_pod_response(response)
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occurred while getting pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get_pod_ip(cls, namespace_name: str, pod_name: str, timeout_seconds: float = POD_IP_TIMEOUT_SECONDS) -> str:
        '''
        Get the IP of the Pod.
        :params: namespace_name: str
        :params: pod_name: str
        :params: timeout_seconds: float
        :returns: str: Pod IP
        '''
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)
                if pod.status.pod_ip:
                    print(f'Pod: {pod_name} IP:', pod.status.pod_ip)
                    return pod.status.pod_ip
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for pod {pod_name} IP address after {timeout_seconds} seconds")

    @classmethod
    def poll_status(cls, namespace_name: str, pod_name: str, target_status: str, timeout_seconds: float = POD_UPTIME_TIMEOUT) -> None:
        '''
        Poll pod status until it matches target_status or timeout is reached.
        
        Args:
            namespace_name: Name of the namespace
            pod_name: Name of the pod
            target_status: Status to wait for (e.g., 'Running', 'Succeeded')
            timeout_seconds: Maximum time to wait in seconds
        
        Raises:
            TimeoutError: If pod doesn't reach target status within timeout
            ApiException: If there's an error getting pod status
        '''
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)
                current_status = pod.status.phase
                print(f'Pod: {pod_name} Status:', current_status)
                if current_status == target_status:
                    return
                elif current_status in ['Failed', 'Unknown']:
                    raise Exception(f'Pod entered {current_status} state')
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for pod {pod_name} to reach status {target_status} after {timeout_seconds} seconds")

    @classmethod
    def poll_container_readiness(cls, namespace_name: str, pod_name: str, container_names: List[str], timeout_seconds: float = CONTAINER_READINESS_TIMEOUT_SECONDS) -> None:
        '''
        Poll container statuses until all specified containers are running or timeout is reached.

        Args:
            namespace_name: Name of the namespace
            pod_name: Name of the pod
            container_names: List of container names to check
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            TimeoutError: If containers don't become running within timeout
            ApiException: If there's an error getting pod status
        '''
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)

                # Check if pod is running first
                if pod.status.phase != 'Running':
                    time.sleep(1)
                    continue

                # Build a map of container statuses
                container_statuses = {}
                if pod.status.container_statuses:
                    for status in pod.status.container_statuses:
                        container_statuses[status.name] = status

                # Check if all required containers are running
                all_running = True
                for container_name in container_names:
                    if container_name not in container_statuses:
                        all_running = False
                        break
                    status = container_statuses[container_name]
                    # Check if container state has 'running' attribute (meaning it's running)
                    if not hasattr(status, 'state') or not status.state:
                        all_running = False
                        break
                    # Check if state.running exists (container is running)
                    # V1ContainerState has attributes: running, waiting, terminated
                    if not hasattr(status.state, 'running') or status.state.running is None:
                        all_running = False
                        break

                if all_running:
                    print(f'All containers in pod {pod_name} are running')
                    return

            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for containers {container_names} in pod {pod_name} to be running after {timeout_seconds} seconds")

    @classmethod
    def save(cls, data: SavePodDataClass) -> dict:
        '''
        Save the pod by creating a Kubernetes Job for snapshot building.
        
        :params:
            data: SavePodDataClass with environment_variables containing container_id and db credentials
        :returns: dict: Image details
        '''
        try:
            cls.check_kubernetes_client()
            # get the pod
            pod: V1Pod = cls.get(GetPodDataClass(namespace_name=data.namespace_name, pod_name=data.pod_name))
            # Pod not found
            if pod == {}:
                raise ApiException(f'Pod {data.pod_name} not found')
            # Pod has no containers
            if pod['associated_resources'] == []:
                raise ApiException(f'Pod {data.pod_name} has no containers')
            # Pod now has main container and status sidecar (snapshot sidecar removed)
            if len(pod['associated_resources']) != 2:
                raise ApiException(f'Pod {data.pod_name} needs a main container and status sidecar container')
            container_names: list[str] = [container['container_name'] for container in pod['associated_resources']]
            if STATUS_SIDECAR_NAME not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a status sidecar container')
            if data.pod_name not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a main container and status sidecar container')

            # Wait for main container to be running before attempting to save
            cls.poll_container_readiness(
                namespace_name=data.namespace_name,
                pod_name=data.pod_name,
                container_names=[data.pod_name],
                timeout_seconds=CONTAINER_READINESS_TIMEOUT_SECONDS
            )

            # save the pod using a Job
            return {**SaveUtility.save_image(data), 'pod_name': data.pod_name, 'namespace_name': data.namespace_name}
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occured: {str(e)}') from e

    @classmethod
    def _update_pod_image(cls, namespace_name: str, pod_name: str, image_name: str) -> None:
        '''
        Update a pod's main container image definition in place.
        The pod will use the new image on its next restart.
        
        :params: namespace_name: str - Namespace of the pod
        :params: pod_name: str - Name of the pod
        :params: image_name: str - New image to use
        '''
        try:
            # Read the current pod
            pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)
            
            # Update the image in the main container only (not the status sidecar)
            for container in pod.spec.containers:
                if container.name != STATUS_SIDECAR_NAME:
                    container.image = image_name
            
            # Patch the pod with the new image
            cls.client.patch_namespaced_pod(
                name=pod_name,
                namespace=namespace_name,
                body=pod
            )
            
            print(f"Updated pod {pod_name} image to {image_name}")
            
        except ApiException as e:
            raise ApiException(f'Error updating pod {pod_name} image: {str(e)}') from e

    @classmethod
    def _ensure_status_sidecar_rbac(cls, namespace_name: str) -> None:
        '''
        Ensure RBAC resources exist for status sidecar pod watching.
        Creates ServiceAccount, Role, and RoleBinding if they don't exist.
        This is idempotent - safe to call multiple times.

        :params: namespace_name: str - Namespace to create RBAC resources in
        '''
        rbac_api: RbacAuthorizationV1Api = RbacAuthorizationV1Api()

        # Create ServiceAccount if it doesn't exist
        try:
            cls.client.read_namespaced_service_account(
                name=STATUS_SIDECAR_SERVICE_ACCOUNT_NAME,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                service_account = V1ServiceAccount(
                    metadata=V1ObjectMeta(
                        name=STATUS_SIDECAR_SERVICE_ACCOUNT_NAME,
                        namespace=namespace_name
                    )
                )
                cls.client.create_namespaced_service_account(namespace_name, service_account)
                print(f'Created ServiceAccount {STATUS_SIDECAR_SERVICE_ACCOUNT_NAME} in namespace {namespace_name}')
            else:
                raise

        # Create Role if it doesn't exist
        try:
            rbac_api.read_namespaced_role(
                name=STATUS_SIDECAR_ROLE_NAME,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                role = V1Role(
                    metadata=V1ObjectMeta(
                        name=STATUS_SIDECAR_ROLE_NAME,
                        namespace=namespace_name
                    ),
                    rules=[
                        V1PolicyRule(
                            api_groups=[''],
                            resources=['pods'],
                            verbs=['get', 'list', 'watch']
                        )
                    ]
                )
                rbac_api.create_namespaced_role(namespace_name, role)
                print(f'Created Role {STATUS_SIDECAR_ROLE_NAME} in namespace {namespace_name}')
            else:
                raise

        # Create RoleBinding if it doesn't exist
        try:
            rbac_api.read_namespaced_role_binding(
                name=STATUS_SIDECAR_ROLE_BINDING_NAME,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                role_binding = V1RoleBinding(
                    metadata=V1ObjectMeta(
                        name=STATUS_SIDECAR_ROLE_BINDING_NAME,
                        namespace=namespace_name
                    ),
                    subjects=[
                        RbacV1Subject(
                            kind='ServiceAccount',
                            name=STATUS_SIDECAR_SERVICE_ACCOUNT_NAME,
                            namespace=namespace_name
                        )
                    ],
                    role_ref=V1RoleRef(
                        api_group='rbac.authorization.k8s.io',
                        kind='Role',
                        name=STATUS_SIDECAR_ROLE_NAME
                    )
                )
                rbac_api.create_namespaced_role_binding(namespace_name, role_binding)
                print(f'Created RoleBinding {STATUS_SIDECAR_ROLE_BINDING_NAME} in namespace {namespace_name}')
            else:
                raise

    @classmethod
    def create(cls, data: CreatePodDataClass) -> dict:
        '''
        Create a pod.
        :params: data: CreatePodDataClass
        :returns: dict: Pod Details
        '''
        try:
            cls.check_kubernetes_client()
            p: dict = cls.get(GetPodDataClass(namespace_name=data.namespace_name, pod_name=data.pod_name))
            if p:
                return p

            # Ensure RBAC resources exist for status sidecar
            cls._ensure_status_sidecar_rbac(data.namespace_name)
            # create environment variable list
            environment_variables: list[V1EnvVar] = [
                V1EnvVar(name=name, value=value)
                for name, value in data.environment_variables.items()
            ]
            # create target port list
            target_ports: list[V1ContainerPort] = [
                V1ContainerPort(container_port=target_port)
                for target_port in data.target_ports
            ]
            # Create volume mounts for snapshot directory
            snapshot_volume_mount = V1VolumeMount(
                name="snapshot-volume",
                mount_path=SNAPSHOT_DIR
            )
            # Build resource requirements from the request's ResourceRequirementsDataClass
            rr: ResourceRequirementsDataClass | None = data.resource_requirements
            requests: dict = {}
            limits: dict = {}
            if rr:
                rr_dict: dict = rr.to_dict()
                # Map dataclass fields to Kubernetes resource keys and bucket (requests/limits)
                field_mapping: dict[str, tuple[str, str]] = {
                    "cpu_request": ("requests", "cpu"),
                    "cpu_limit": ("limits", "cpu"),
                    "memory_request": ("requests", "memory"),
                    "memory_limit": ("limits", "memory"),
                    "ephemeral_request": ("requests", "ephemeral-storage"),
                    "ephemeral_limit": ("limits", "ephemeral-storage"),
                }
                for field_name, (bucket, k8s_key) in field_mapping.items():
                    value = rr_dict.get(field_name)
                    if not value:
                        continue
                    if bucket == "requests":
                        requests[k8s_key] = value
                    else:
                        limits[k8s_key] = value

            resource_requirements_k8s: V1ResourceRequirements | None = None
            if requests or limits:
                resource_requirements_k8s = V1ResourceRequirements(
                    requests=requests or None,
                    limits=limits or None,
                )

            containers: list[V1Container] = [
                V1Container(
                    name=data.pod_name,
                    image=data.image_name,
                    ports=target_ports,
                    env=environment_variables,
                    security_context=V1SecurityContext(
                        privileged=False  # No longer needs privileged access
                    ),
                    volume_mounts=[snapshot_volume_mount],
                    resources=resource_requirements_k8s or None,
                ),
                V1Container(
                    name=STATUS_SIDECAR_NAME,
                    image=STATUS_SIDECAR_IMAGE_NAME,
                    security_context=V1SecurityContext(
                        privileged=False  # No longer needs privileged access
                    ),
                    env=environment_variables,
                    resources=resource_requirements_k8s or None,
                )
                # Snapshot sidecar removed - snapshots now handled by Kubernetes Jobs
            ]
            # Create volumes for the pod, with optional snapshot size limit
            empty_dir_kwargs: dict = {}
            if rr and rr.snapshot_size_limit:
                empty_dir_kwargs["size_limit"] = rr.snapshot_size_limit
            volumes = [
                V1Volume(
                    name="snapshot-volume",
                    empty_dir=V1EmptyDirVolumeSource(**empty_dir_kwargs),
                )
            ]

            # create pod manifest
            pod_manifest: V1Pod = V1Pod(
                metadata=V1ObjectMeta(
                    name=data.pod_name,
                    labels={"app": data.container_name},  # Use base name for label (constant)
                    annotations={
                        "nginx.org/websocket-services": data.container_name,  # Use base name
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600"  # for websockets
                    }
                ),
                spec=V1PodSpec(
                    service_account_name=STATUS_SIDECAR_SERVICE_ACCOUNT_NAME,
                    security_context=V1SecurityContext(
                        privileged=True
                    ),
                    volumes=volumes,
                    containers=containers
                )
            )
            # create the actual pod
            pod: V1Pod = cls.client.create_namespaced_pod(data.namespace_name, pod_manifest)
            # wait for the pod status to be running
            cls.poll_status(namespace_name=data.namespace_name, pod_name=data.pod_name, target_status='Running')
            return cls.get_pod_response(pod)
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, pod_name: str, timeout_seconds: float = POD_TERMINATION_TIMEOUT) -> None:
        '''
        Poll pod termination.
        :params: namespace_name: str
        :params: pod_name: str
        :params: timeout_seconds: float
        '''
        is_terminated: bool = False
        while is_terminated != True:
            pod: dict = cls.get(GetPodDataClass(**{'namespace_name': namespace_name, 'pod_name': pod_name}))
            is_terminated = (pod == {})
            print(f'Pod: {pod_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeletePodDataClass) -> dict:
        '''
        Delete a pod.
        :params: data: DeletePodDataClass
        :returns: dict: Status
        '''
        try:
            cls.check_kubernetes_client()
            cls.client.delete_namespaced_pod(data.pod_name, data.namespace_name)
            cls.poll_termination(data.namespace_name, data.pod_name) # wait for pod to be deleted, otherwise list pod will find it and integration tests will fail..
            return {'status': 'success'}
        except ApiException as ae:
            raise ApiException(f'Error occured while deleting pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e
