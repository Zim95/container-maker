# modules
import time
from src.resources.dataclasses.namespace.get_namespace_dataclass import GetNamespaceDataClass
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.common.exceptions import UnsupportedRuntimeEnvironment

# third party
from kubernetes.client import V1Namespace
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1NetworkPolicy
from kubernetes.client import V1NetworkPolicyIngressRule
from kubernetes.client import NetworkingV1Api
from kubernetes.client.rest import ApiException


class NamespaceManager(KubernetesResourceManager):
    '''
    Manage kubernetes namespaces.
    '''
    @classmethod
    def list(cls) -> list[dict]:
        '''
        List all available namespaces.
        :params: None
        :returns: list[dict]: List of namespaces
        '''
        try:
            cls.check_kubernetes_client()
            return [
                {
                    'namespace_id': ns.metadata.uid,
                    'namespace_name': ns.metadata.name,
                }
                for ns in cls.client.list_namespace().items
            ]
        except ApiException as ae:
            raise ApiException(f'Error occured while listing namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def get(cls, data: GetNamespaceDataClass) -> dict:
        '''
        Get a namespace.
        :params: data: GetNamespaceDataClass
        :returns: dict: Namespace Details
        '''
        try:
            cls.check_kubernetes_client()
            response: V1Namespace = cls.client.read_namespace(name=data.namespace_name)
            return {
                'namespace_id': response.metadata.uid,
                'namespace_name': response.metadata.name,
            }
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occured while getting namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def create(cls, data: CreateNamespaceDataClass) -> dict:
        '''
        Create a namespace. Return if already exists.
        :params: data: CreateNamespaceDataClass
        :returns: dict: Namespace Details
        '''
        try:
            ns: dict = cls.get(GetNamespaceDataClass(namespace_name=data.namespace_name))
            if ns:
                return ns
            namespace: V1Namespace = V1Namespace(
                metadata=V1ObjectMeta(name=data.namespace_name)
            )
            cls.client.create_namespace(namespace)
            network_policy: V1NetworkPolicy = V1NetworkPolicy(
                metadata=V1ObjectMeta(name=data.namespace_name),
                spec={
                    "podSelector": {},
                    "policyTypes": ["Ingress"],
                    "ingress": [V1NetworkPolicyIngressRule(_from=None)]
                }
            )
            networking_api: NetworkingV1Api = NetworkingV1Api()
            response: V1NetworkPolicy = networking_api.create_namespaced_network_policy(data.namespace_name, network_policy)
            return {
                'namespace_id': response.metadata.uid,
                'namespace_name': response.metadata.name
            }
        except ApiException as ae:
            raise ApiException(f'Error occured while creating namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, timeout_seconds: float = 2.0) -> None:
        '''
        Poll the termination of a namespace.
        '''
        is_terminated: bool = False
        while is_terminated != True:
            ns: dict = cls.get(GetNamespaceDataClass(namespace_name=namespace_name))
            is_terminated = (ns == {})
            print(f'Namespace: {namespace_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeleteNamespaceDataClass) -> dict:
        '''
        Delete a namespace.
        :params: namespace_name: str
        :returns: dict: Deletion status
        '''
        try:
            cls.check_kubernetes_client()
            # Call Kubernetes API to delete the namespace
            deletion_response = cls.client.delete_namespace(data.namespace_name)
            cls.poll_termination(data.namespace_name)
            return {"status": "success", "message": f"Namespace '{data.namespace_name}' deleted.", "details": deletion_response.to_dict()}
        except ApiException as ae:
            raise ApiException(f"Error occurred while deleting namespace '{data.namespace_name}': {str(ae)}") from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f"Unsupported Runtime Environment: {str(ure)}") from ure
        except Exception as e:
            raise Exception(f"Unknown error occurred: {str(e)}") from e
