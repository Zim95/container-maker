# builtins
import time

# kubernetes
from kubernetes.client import V1Pod, V1ObjectMeta, V1PodSpec, V1Container, V1VolumeMount, V1Volume
from kubernetes.client import V1PersistentVolumeClaimVolumeSource
from kubernetes.client.rest import ApiException
from kubernetes.client import V1PersistentVolumeClaim, V1PersistentVolumeClaimSpec, V1ResourceRequirements

# modules
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.nfs.create_nfs_dataclass import CreateNFSDataClass
from src.resources.dataclasses.nfs.delete_nfs_dataclass import DeleteNFSDataClass
from src.resources.dataclasses.nfs.get_nfs_dataclass import GetNFSDataClass
from src.resources.dataclasses.nfs.list_nfs_dataclass import ListNFSDataClass
from src.resources.resource_config import POD_IP_TIMEOUT_SECONDS
from src.common.exceptions import UnsupportedRuntimeEnvironment


class NFSManager(KubernetesResourceManager):
    """
    Manage NFS resources in Kubernetes.
    """

    @classmethod
    def get_nfs_ip(cls, namespace_name: str, nfs_name: str, timeout_seconds: float = POD_IP_TIMEOUT_SECONDS) -> str:
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=nfs_name, namespace=namespace_name)
                if pod.status.pod_ip:
                    return pod.status.pod_ip
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for nfs pod {nfs_name} IP address after {timeout_seconds} seconds")

    @classmethod
    def list(cls, data: ListNFSDataClass) -> list[dict]:
        """
        List NFS servers.
        :params:
            :data: ListResourceDataClass
        :returns: list[dict]: List of NFS resources
        """
        try:
            cls.check_kubernetes_client()
        except ApiException as ae:
            raise ApiException(f'Error occurred while listing nfs pods: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get(cls, data: GetNFSDataClass) -> dict:
        """
        Get an NFS server by its name and namespace.
        :params:
            :data: GetResourceDataClass
        :returns: dict: Info of the NFS server
        """
        try:
            cls.check_kubernetes_client()
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occurred while getting nfs pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def create(cls, data: CreateNFSDataClass) -> dict:
        """
        Create an NFS server in the cluster.
        :params:
            :data: CreateResourceDataClass
        :returns: dict: Info of the created NFS resource
        """
        try:
            cls.check_kubernetes_client()
        except ApiException as ae:
            raise ApiException(f'Error occured while creating nfs pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, nfs_name: str, timeout_seconds: float = 2.0) -> None:
        is_terminated: bool = False
        while is_terminated != True:
            pod: dict = cls.get(GetNFSDataClass(**{'namespace_name': namespace_name, 'nfs_name': nfs_name}))
            is_terminated = (pod == {})
            print(f'NFS: {nfs_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeleteNFSDataClass) -> dict:
        """
        Delete an NFS server from the cluster.
        :params:
            :data: DeleteResourceDataClass
        :returns: dict: Info of the deleted NFS resource
        """
        try:
            cls.check_kubernetes_client()
        except ApiException as ae:
            raise ApiException(f'Error occured while deleting nfs pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e
