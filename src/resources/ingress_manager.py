# builtins
import time

# modules
from src.resources.dataclasses.ingress.create_ingress_dataclass import CreateIngressDataClass
from src.resources.dataclasses.ingress.delete_ingress_dataclass import DeleteIngressDataClass
from src.resources.dataclasses.ingress.get_ingress_dataclass import GetIngressDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources import KubernetesResourceManager
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.resources.resource_config import INGRESS_IP_TIMEOUT_SECONDS

# third party
from kubernetes.client.rest import ApiException
from kubernetes.client.models import V1Ingress
from kubernetes.client import NetworkingV1Api


class IngressManager(KubernetesResourceManager):
    '''
    Manage kubernetes ingress.
    '''

    @classmethod
    def check_kubernetes_client(cls) -> None:
        '''
        Check if the kubernetes client exists.
        If so overwrite the client with NetworkingV1Api.
        '''
        super().check_kubernetes_client()
        cls.client = NetworkingV1Api()

    @classmethod
    def list(cls, data: ListIngressDataClass) -> list[dict]:
        '''
        List all ingress in a namespace.
        '''
        try:
            cls.check_kubernetes_client()
            return [
                {
                    'ingress_id': ingress.metadata.uid,
                    'ingress_name': ingress.metadata.name,
                    'ingress_namespace': ingress.metadata.namespace,
                    'ingress_ip': (
                        ingress.status.load_balancer.ingress[0].ip or 
                        ingress.status.load_balancer.ingress[0].hostname
                        if ingress.status.load_balancer.ingress else None
                    ),
                }
                for ingress in cls.client.list_namespaced_ingress(data.namespace_name).items
            ]
        except ApiException as ae:
            raise ApiException(f'Error occured while listing ingress: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def get(cls, data: GetIngressDataClass) -> dict:
        '''
        Get an ingress.
        '''
        try:
            cls.check_kubernetes_client()
            response: V1Ingress = cls.client.read_namespaced_ingress(data.ingress_name, data.namespace_name)
            return {
                'ingress_id': response.metadata.uid,
                'ingress_name': response.metadata.name,
                'ingress_namespace': response.metadata.namespace,
                'ingress_ip': (
                    response.status.load_balancer.ingress[0].ip or 
                    response.status.load_balancer.ingress[0].hostname
                    if response.status.load_balancer.ingress else None
                ),
            }
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occured while getting ingress: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def get_ingress_ip(cls, namespace_name: str, ingress_name: str, timeout_seconds: float = INGRESS_IP_TIMEOUT_SECONDS) -> str:
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                ingress = cls.client.read_namespaced_ingress(name=ingress_name, namespace=namespace_name)
                print(ingress.status.load_balancer.ingress)
                if ingress.status.load_balancer.ingress:
                    # Try IP first, then hostname if IP is not available
                    return (ingress.status.load_balancer.ingress[0].ip or 
                           ingress.status.load_balancer.ingress[0].hostname)
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for ingress {ingress_name} IP/hostname after {timeout_seconds} seconds")

    @classmethod
    def create(cls, data: CreateIngressDataClass) -> dict:
        '''
        Create an ingress or return an existing ingress.
        '''
        try:
            cls.check_kubernetes_client()
            i: dict = cls.get(GetIngressDataClass(ingress_name=data.ingress_name, namespace_name=data.namespace_name))
            if i:
                return i
            # Prepare the ingress manifest
            ingress_manifest = {
                "apiVersion": "networking.k8s.io/v1",
                "kind": "Ingress",
                "metadata": {
                    "name": data.ingress_name,
                    "namespace": data.namespace_name,
                    "annotations": {
                        "nginx.ingress.kubernetes.io/rewrite-target": "/",
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-connect-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/websocket-services": data.service_name # for websockets
                    }
                },
                "spec": {
                    "ingressClassName": "nginx",
                    "rules": [
                        {
                            "host": data.host,
                            "http": {
                                "paths": [
                                    {
                                        "path": data.path,
                                        "pathType": "Prefix",
                                        "backend": {
                                            "service": {
                                                "name": data.service_name,
                                                "port": {"number": data.service_port},
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }
            }

            # Remove None values for optional fields
            ingress_manifest["spec"] = {k: v for k, v in ingress_manifest["spec"].items() if v is not None}

            # Create the ingress
            ingress: V1Ingress = cls.client.create_namespaced_ingress(
                namespace=data.namespace_name,
                body=ingress_manifest
            )

            # Return a summary of the created ingress
            return {
                'ingress_id': ingress.metadata.uid,
                'ingress_name': ingress.metadata.name,
                'ingress_namespace': ingress.metadata.namespace,
                'ingress_ip': cls.get_ingress_ip(data.namespace_name, data.ingress_name),
            }
        except ApiException as ae:
            raise ApiException(f'Error occured while creating ingress: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, ingress_name: str, timeout_seconds: float = 2.0) -> None:
        is_terminated: bool = False
        while is_terminated != True:
            ingress: dict = cls.get(GetIngressDataClass(namespace_name=namespace_name, ingress_name=ingress_name))
            is_terminated = (ingress == {})
            print(f'Ingress: {ingress_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeleteIngressDataClass) -> dict:
        '''
        Delete an ingress.
        '''
        try:
            cls.check_kubernetes_client()
            cls.client.delete_namespaced_ingress(data.ingress_name, data.namespace_name)
            cls.poll_termination(data.namespace_name, data.ingress_name) # wait for ingress to be deleted, otherwise list ingress will find it and integration tests will fail..
            return {'status': 'success'}
        except ApiException as ae:
            raise ApiException(f'Error occured while deleting ingress: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e
