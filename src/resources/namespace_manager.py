# modules
import time
from src.resources.dataclasses.namespace.get_namespace_dataclass import GetNamespaceDataClass
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.common.logging_setup import get_logger
from src.resources.manifest_loader import render_manifests
from src.resources.resource_config import POD_CIDR, SERVICE_CIDR

# third party
from kubernetes.client import V1Namespace
from kubernetes.client import V1ObjectMeta
from kubernetes.client import NetworkingV1Api
from kubernetes.client.rest import ApiException

logger = get_logger("namespace_manager")


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
            created: V1Namespace = cls.client.create_namespace(namespace)
            # Apply the isolation NetworkPolicies for this per-user namespace.
            cls._apply_network_policies(data.namespace_name)
            return {
                'namespace_id': created.metadata.uid,
                'namespace_name': created.metadata.name
            }
        except ApiException as ae:
            raise ApiException(f'Error occured while creating namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def _apply_network_policies(cls, namespace_name: str) -> None:
        '''
        Apply the per-user-namespace isolation NetworkPolicies from the manifest template
        (src/resources/manifests/user_namespace_netpol.yaml): default-deny + narrow allows for DNS,
        socket-ssh ingress on :22, Postgres egress, and internet egress (minus the cluster CIDRs).
        Idempotent (409 = already exists is ignored).
        NOTE: only ENFORCED by a policy-capable CNI (Calico/Cilium); docker-desktop accepts but
        does not enforce them.
        '''
        docs: list[dict] = render_manifests(
            "user_namespace_netpol.yaml",
            {"NAMESPACE": namespace_name, "POD_CIDR": POD_CIDR, "SERVICE_CIDR": SERVICE_CIDR},
        )
        networking_api: NetworkingV1Api = NetworkingV1Api()
        for doc in docs:
            try:
                networking_api.create_namespaced_network_policy(namespace=namespace_name, body=doc)
            except ApiException as ae:
                if ae.status == 409:  # already exists — idempotent re-apply
                    continue
                raise
        logger.info("applied network policies", extra={"namespace_name": namespace_name, "count": len(docs)})

    @classmethod
    def poll_termination(cls, namespace_name: str, timeout_seconds: float = 2.0) -> None:
        '''
        Poll the termination of a namespace.
        '''
        is_terminated: bool = False
        while is_terminated != True:
            ns: dict = cls.get(GetNamespaceDataClass(namespace_name=namespace_name))
            is_terminated = (ns == {})
            logger.info("polling namespace termination", extra={"namespace_name": namespace_name, "is_terminated": is_terminated})
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
