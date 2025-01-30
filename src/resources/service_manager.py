# builtins
import time

# modules
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources import KubernetesResourceManager
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.resources.pod_manager import PodManager
from src.resources.resource_config import SERVICE_IP_TIMEOUT_SECONDS

# third party
from kubernetes.client.rest import ApiException
from kubernetes.client import V1Service
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1ServiceSpec
from kubernetes.client import V1ServicePort


class ServiceManager(KubernetesResourceManager):
    '''
    Manage kubernetes services.
    '''

    @classmethod
    def get_associated_pods(cls, service: dict) -> list[dict]:
        '''
        Get associated pods for a service by matching the service's selector labels
        with pod labels.
        '''
        pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': service.get('metadata', {}).get('namespace', '')}))
        service_selector = service.get('spec', {}).get('selector', {})
        return [
            pod for pod in pods
            if pod.get('pod_name') == service_selector.get('app', '')
        ]

    @classmethod
    def list(cls, data: ListServiceDataClass) -> list[V1Service]:
        try:
            cls.check_kubernetes_client()
            return [
                {
                    'service_id': service.metadata.uid,
                    'service_name': service.metadata.name,
                    'service_namespace': service.metadata.namespace,
                    'service_ip': service._spec.cluster_ip,
                    'service_target_port': service._spec.ports[0].target_port,
                    'service_port': service._spec.ports[0].port,
                    'associated_pods': cls.get_associated_pods(service.to_dict()),
                }
                for service in cls.client.list_namespaced_service(namespace=data.namespace_name).items
            ]
        except ApiException as ae:
            raise ApiException(f'Error occurred while listing services: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get(cls, data: GetServiceDataClass) -> V1Service:
        try:
            cls.check_kubernetes_client()
            response: V1Service = cls.client.read_namespaced_service(name=data.service_name, namespace=data.namespace_name)
            return {
                'service_id': response.metadata.uid,
                'service_name': response.metadata.name,
                'service_namespace': response.metadata.namespace,
                'service_ip': response._spec.cluster_ip,
                'service_target_port': response._spec.ports[0].target_port,
                'service_port': response._spec.ports[0].port,
                'associated_pods': cls.get_associated_pods(response.to_dict()),
            }
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occured while getting service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get_service_ip(cls, namespace_name: str, service_name: str, timeout_seconds: float = SERVICE_IP_TIMEOUT_SECONDS) -> str:
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                service = cls.client.read_namespaced_service(name=service_name, namespace=namespace_name)
                if service._spec.cluster_ip:
                    return service._spec.cluster_ip
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for service {service_name} IP address after {timeout_seconds} seconds")

    @classmethod
    def create(cls, data: CreateServiceDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            # check for existing services
            s: dict = cls.get(GetServiceDataClass(**{'namespace_name': data.namespace_name, 'service_name': data.service_name}))
            if s:
                return s

            # create the service manifest
            service_manifest: V1Service = V1Service(
                metadata=V1ObjectMeta(
                    name=data.service_name,
                    annotations={
                        "nginx.org/websocket-services": data.service_name,  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600"  # for websockets
                    }
                ),
                spec=V1ServiceSpec(
                    selector={"app": data.pod_name},
                    ports=[
                        V1ServicePort(
                            port=data.service_port,
                            target_port=data.target_port,
                            protocol=data.protocol
                        )
                    ],
                    type="LoadBalancer"
                )
            )
            # create the service
            service: V1Service = cls.client.create_namespaced_service(data.namespace_name, service_manifest)
            # return the details
            return {
                "service_id": service.metadata.uid,
                "service_ip": cls.get_service_ip(data.namespace_name, data.service_name),
                "service_name": service.metadata.name,
                "service_namespace": service.metadata.namespace,
                "service_target_port": service._spec.ports[0].target_port,
                "service_port": service._spec.ports[0].port,
                "associated_pods": cls.get_associated_pods(service.to_dict()),
            }
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, service_name: str, timeout_seconds: float = 2.0) -> None:
        is_terminated: bool = False
        while is_terminated != True:
            service: dict = cls.get(GetServiceDataClass(**{'namespace_name': namespace_name, 'service_name': service_name}))
            is_terminated = (service == {})
            print(f'Service: {service_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeleteServiceDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            cls.client.delete_namespaced_service(data.service_name, data.namespace_name)
            cls.poll_termination(data.namespace_name, data.service_name) # wait for service to be deleted, otherwise list service will find it and integration tests will fail..
            return {'status': 'success'}
        except ApiException as ae:
            raise ApiException(f'Error occurred while deleting service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e 
