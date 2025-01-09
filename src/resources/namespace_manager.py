# modules
from src.resources.resource_manager import KubernetesResourceManager
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
        List a number of available namespaces.
        :params: None
        :returns: None
        '''
        try:
            cls.check_kubernetes_client()
            return cls.client.list_namespace().items
        except ApiException as ae:
            raise ApiException(f'Error occured while listing namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def create(cls, data: CreateNamespaceDataClass) -> dict:
        '''
        Create a namespace.
        :params: data: CreateNamespaceDataClass
        :returns: dict: Namespace Details
        '''
        try:
            namespaces: list[dict] = cls.list()
            for ns in namespaces:
                if ns.metadata.name == data.namespace_name:
                    return ns
            namespace: V1Namespace = V1Namespace(
                metadata=V1ObjectMeta(name=data.namespace_name)
            )
            cls.client.create_namespace(namespace)
            network_policy: V1NetworkPolicy = V1NetworkPolicy(
                metadata={"name": "deny-from-other-namespaces"},
                spec={
                    "podSelector": {},
                    "policyTypes": ["Ingress"],
                    "ingress": [V1NetworkPolicyIngressRule(_from=None)]
                }
            )
            networking_api: NetworkingV1Api = NetworkingV1Api()
            return networking_api.create_namespaced_network_policy(data.namespace_name, network_policy)
        except ApiException as ae:
            raise ApiException(f'Error occured while creating namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

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
            return {"status": "success", "message": f"Namespace '{data.namespace_name}' deleted.", "details": deletion_response.to_dict()}
        except ApiException as ae:
            raise ApiException(f"Error occurred while deleting namespace '{data.namespace_name}': {str(ae)}") from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f"Unsupported Runtime Environment: {str(ure)}") from ure
        except Exception as e:
            raise Exception(f"Unknown error occurred: {str(e)}") from e
