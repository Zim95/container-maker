# builtins
from collections import defaultdict
import time

# modules
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass, ServiceType
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources import KubernetesResourceManager
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.resources.pod_manager import PodManager
from src.resources.resource_config import SERVICE_IP_TIMEOUT_SECONDS, SERVICE_TERMINATION_TIMEOUT, SNAPSHOT_SIDECAR_NAME

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
        :params: service: dict
        :returns: list[dict]: List of pods
        '''
        pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': service.get('metadata', {}).get('namespace', '')}))
        service_selector: dict = service.get('spec', {}).get('selector', {})
        if not service_selector:
            return []
        return [
            pod for pod in pods
            if all(
                pod.get('pod_labels', {}).get(key) == value
                for key, value in service_selector.items()
            )
        ]

    @classmethod
    def get_service_ports(cls, service: V1Service) -> list[dict]:
        """
        Get all ports from a service.
        :params: service: V1Service
        :returns: list[dict]: List of ports
        """
        ports: list[dict] = []
        for port in service._spec.ports:
            ports.append({
                'name': port.name if port.name else None,  # Optional port name
                'container_port': port.port,  # The service port will be the container port
                'protocol': port.protocol if port.protocol else None  # TCP/UDP
            })
        return ports

    @classmethod
    def list(cls, data: ListServiceDataClass) -> list[V1Service]:
        '''
        List all services in a namespace.
        :params: data: ListServiceDataClass
        :returns: list[dict]: List of services
        '''
        try:
            cls.check_kubernetes_client()
            return [
                {
                    'service_id': service.metadata.uid,
                    'service_name': service.metadata.name,
                    'service_namespace': service.metadata.namespace,
                    'service_ip': service._spec.cluster_ip,
                    'service_ports': cls.get_service_ports(service),
                    'service_type': service.spec.type,
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
        '''
        Get a service.
        :params: data: GetServiceDataClass
        :returns: dict: Service Details
        '''
        try:
            cls.check_kubernetes_client()
            response: V1Service = cls.client.read_namespaced_service(name=data.service_name, namespace=data.namespace_name)
            return {
                'service_id': response.metadata.uid,
                'service_name': response.metadata.name,
                'service_namespace': response.metadata.namespace,
                'service_ip': response._spec.cluster_ip,
                'service_ports': cls.get_service_ports(response),
                'service_type': response.spec.type,
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
        '''
        Get the service IP.
        :params: namespace_name: str
        :params: service_name: str
        :params: timeout_seconds: float
        :returns: str: Service IP
        '''
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
    def get_v1_service_ports(cls, data: CreateServiceDataClass) -> list:
        '''
        Get the v1 service ports.
        :params: data: CreateServiceDataClass
        :returns: list: List of v1 service ports
        '''
        publish_port_counter: defaultdict = defaultdict(int)
        target_port_counter: defaultdict = defaultdict(int)
        ports: list = []

        for pi in data.publish_information:
            service_port: int = pi.publish_port
            target_port: int = pi.target_port
            protocol: str = pi.protocol
            node_port: int = pi.node_port if data.service_type == ServiceType.NODE_PORT else None
            publish_port_counter[service_port] += 1
            target_port_counter[target_port] += 1
            if publish_port_counter[service_port] > 1:
                raise Exception(f'Duplicate publish port: {service_port}. Cannot have duplicate ports')
            if target_port_counter[target_port] > 1:
                raise Exception(f'Duplicate target port: {target_port}. Cannot have duplicate ports')
            ports.append(
                V1ServicePort(
                    port=service_port,
                    target_port=target_port,
                    protocol=protocol,
                    node_port=node_port
                )
            )
        return ports

    @classmethod
    def create(cls, data: CreateServiceDataClass) -> dict:
        '''
        Create a service.
        :params: data: CreateServiceDataClass
        :returns: dict: Service Details
        '''
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
                ),
                spec=V1ServiceSpec(
                    selector={"app": data.pod_name},
                    ports=cls.get_v1_service_ports(data),
                    type=data.service_type.value if data.service_type else ServiceType.LOAD_BALANCER.value
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
                "service_ports": cls.get_service_ports(service),
                "service_type": service.spec.type,
                "associated_pods": cls.get_associated_pods(service.to_dict()),
            }
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, service_name: str, timeout_seconds: float = SERVICE_TERMINATION_TIMEOUT) -> None:
        '''
        Poll service termination.
        :params: namespace_name: str
        :params: service_name: str
        :params: timeout_seconds: float
        '''
        is_terminated: bool = False
        while is_terminated != True:
            service: dict = cls.get(GetServiceDataClass(**{'namespace_name': namespace_name, 'service_name': service_name}))
            is_terminated = (service == {})
            print(f'Service: {service_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def save_service_pods(cls, data: GetServiceDataClass) -> list:
        '''
        Save all pods associated with a service.
        :params: data: SaveServiceDataClass
        :returns: list[dict]: List of pods
        '''
        # get the service
        service: V1Service = cls.client.read_namespaced_service(name=data.service_name, namespace=data.namespace_name)
        # get the associated pods
        pods: list[dict] = cls.get_associated_pods(service.to_dict())

        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as worker:
            # Submit all save operations to run in parallel
            futures: list = []
            for pod in pods:
                future = worker.submit(
                    PodManager.save, 
                    SavePodDataClass(
                        namespace_name=data.namespace_name,
                        pod_name=pod['pod_name'],
                        sidecar_pod_name=SNAPSHOT_SIDECAR_NAME,
                    )
                )
                futures.append(future)
            
            # Wait for all save operations to complete
            results: list = []
            for future in futures:
                try:
                    result = future.result()  # This will raise any exceptions that occurred
                    results.append(result)
                except Exception as e:
                    print(f"Save failed for pod: {str(e)}")
            return results

    @classmethod
    def delete(cls, data: DeleteServiceDataClass) -> dict:
        '''
        Delete a service.
        :params: data: DeleteServiceDataClass
        :returns: dict: Status
        '''
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
