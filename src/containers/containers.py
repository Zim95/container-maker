# builtins
from collections import defaultdict

# modules
import src.common.config as config

# dataclasses
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.containers.dataclasses.list_container_dataclass import ListContainerDataClass
from src.containers.dataclasses.get_container_dataclass import GetContainerDataClass
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass

# resources
from src.resources.dataclasses.ingress.create_ingress_dataclass import CreateIngressDataClass
from src.resources.dataclasses.ingress.delete_ingress_dataclass import DeleteIngressDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass, PublishInformationDataClass, ServiceType
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager
from src.resources.ingress_manager import IngressManager
from src.containers import ContainerManager

# kubernetes
from kubernetes.client.exceptions import ApiException


class KubernetesContainerHelper:
    '''
    Helper class for Kubernetes Container Manager.
    '''

    @classmethod
    def check_pod(cls, namespace_name: str, container_id: str) -> dict | None:
        '''
        Check if id of the container is pod.
        '''
        pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': namespace_name}))
        for pod in pods:
            if container_id == pod['pod_id']:
                return pod
        return None

    @classmethod
    def check_service(cls, namespace_name: str, container_id: str) -> dict | None:
        '''
        Check if id of the container is service.
        '''
        services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': namespace_name}))
        for service in services:
            if container_id == service['service_id']:
                return service
        return None

    @classmethod
    def check_ingress(cls, namespace_name: str, container_id: str) -> dict | None:
        '''
        Check if id of the container is ingress.
        Use list method, since, we get id and namespace in data but not the actual name of the ingress.
        '''
        ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': namespace_name}))
        for ingress in ingresses:
            if container_id == ingress['ingress_id']:
                return ingress
        return None

    @classmethod
    def delete_lingering_services(cls, namespace_name: str) -> None:
        services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': namespace_name}))
        for svc in services:
            if not svc.get('associated_pods', []):
                ServiceManager.delete(DeleteServiceDataClass(
                    namespace_name=namespace_name,
                    service_name=svc['service_name'],
                ))

    @classmethod
    def delete_lingering_ingresses(cls, namespace_name: str) -> None:
        ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': namespace_name}))
        for ing in ingresses:
            if not ing.get('associated_services', []):
                IngressManager.delete(DeleteIngressDataClass(
                    namespace_name=namespace_name,
                    ingress_name=ing['ingress_name'],
                ))


class KubernetesContainerManager(ContainerManager):
    '''
    Kubernetes Container Manager
    '''

    helper: KubernetesContainerHelper = KubernetesContainerHelper()

    @classmethod
    def list(cls, data: ListContainerDataClass) -> list[dict]:
        '''
        List all pods, services and ingresses.
        Services inside the ingress are not listed only ingresses are listed.
        Pods inside the service are not listed only services are listed.
        '''
        ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': data.network_name}))
        ingress_services: list = [service for ingress in ingresses for service in ingress.get('associated_services', [])]
        ingress_pods: list = [pod for service in ingress_services for pod in service.get('associated_pods', [])]
        ingress_services_ids: list = [service['service_id'] for service in ingress_services]
        ingress_pods_ids: list = [pod['pod_id'] for pod in ingress_pods]

        services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': data.network_name}))
        unique_services: list = [service for service in services if service['service_id'] not in ingress_services_ids]
        unique_service_pods: list = [pod for service in unique_services for pod in service.get('associated_pods', [])]
        unique_service_pods_ids: list = [pod['pod_id'] for pod in unique_service_pods]

        pod_ids_to_exclude: list = ingress_pods_ids + unique_service_pods_ids

        pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': data.network_name}))
        unique_pods: list = [pod for pod in pods if pod['pod_id'] not in pod_ids_to_exclude]

        containers: list = []
        for ingress in ingresses:
            containers.append(
                {
                    'container_id': ingress['ingress_id'],
                    'container_name': ingress['ingress_name'],
                    'container_ip': ingress['ingress_ip'],
                    'container_network': ingress['ingress_namespace'],
                    'container_port': ingress['ingress_ports'],
                }
            )
        for service in unique_services:
            containers.append(
                {
                    'container_id': service['service_id'],
                    'container_name': service['service_name'],
                    'container_ip': service['service_ip'],
                    'container_network': service['service_namespace'],
                    'container_port': service['service_port']
                }
            )
        for pod in unique_pods:
            containers.append(
                {
                    'container_id': pod['pod_id'],
                    'container_name': pod['pod_name'],
                    'container_ip': pod['pod_ip'],
                    'container_network': pod['pod_namespace'],
                    'container_port': pod['pod_port']
                }
            )
        return containers

    @classmethod
    def get(cls, data: GetContainerDataClass) -> None:
        '''
        Check if id of the container is pod, service or ingress.
        '''
        pod: dict | None = KubernetesContainerHelper.check_pod(namespace_name=data.network_name, container_id=data.container_id)
        service: dict | None = KubernetesContainerHelper.check_service(namespace_name=data.network_name, container_id=data.container_id)
        ingress: dict | None = KubernetesContainerHelper.check_ingress(namespace_name=data.network_name, container_id=data.container_id)
        final_container: dict = pod or service or ingress or {}

        if not final_container:
            raise Exception(f'Cannot find, container_id={data.container_id} in namespace={data.network_name}')

        # get keys
        id_key: str = [key for key in final_container.keys() if key.endswith('_id')][0]
        ip_key: str = [key for key in final_container.keys() if key.endswith('_ip')][0]
        name_key: str = [key for key in final_container.keys() if key.endswith('_name')][0]
        network_key: str = [key for key in final_container.keys() if key.endswith('_namespace')][0]
        ports_key: str = [key for key in final_container.keys() if key.endswith('_ports')][0]

        # final value
        return {
            'container_id': final_container[id_key],
            'container_name': final_container[name_key],
            'container_ip': final_container[ip_key],
            'container_network': final_container[network_key],
            'container_ports': final_container[ports_key],
        }

    @classmethod
    def validate_publish_information(cls, publish_information: list) -> None:
        unique_target_ports: dict = defaultdict(int)
        unique_publish_ports: dict = defaultdict(int)
        for p in publish_information:
            unique_target_ports[p.target_port] += 1
            unique_publish_ports[p.publish_port] += 1
            if unique_target_ports[p.target_port] > 1:
                raise ValueError(f'Duplicate target port: {p.target_port}')
            if unique_publish_ports[p.publish_port] > 1:
                raise ValueError(f'Duplicate publish port: {p.publish_port}')

    @classmethod
    def create(cls, data: CreateContainerDataClass) -> dict:
        '''
        Create a container.
        Create the namespace. If it already exists, use it.
        First create the pod.
        Then if,
        - Exposure level is greater than ExposureLevel.CLUSTER_LOCAL, create the service of type ClusterIP.
        - Exposure level is greater than ExposureLevel.CLUSTER_EXTERNAL, create the service of type LoadBalancer.
        - Exposure level is greater than ExposureLevel.EXPOSED, create the ingress.
        '''
        try:
            NamespaceManager.create(CreateNamespaceDataClass(namespace_name=data.network_name))
            cls.validate_publish_information(data.publish_information)
            final_container: dict = {}
            # create the pod.
            pod: dict = PodManager.create(CreatePodDataClass(
                image_name=data.image_name,
                pod_name=f'{data.container_name}-pod',
                namespace_name=data.network_name,
                target_ports={pi.target_port for pi in data.publish_information},
                environment_variables=data.environment_variables,
            ))
            final_container = pod
            # create the service if exposure level is greater than ExposureLevel.INTERNAL
            if data.exposure_level.value > ExposureLevel.INTERNAL.value:
                service_type: ServiceType = (
                    ServiceType.LOAD_BALANCER if data.exposure_level.value > ExposureLevel.CLUSTER_LOCAL.value
                    else ServiceType.CLUSTER_IP
                )
                service: dict = ServiceManager.create(CreateServiceDataClass(
                    service_name=f'{data.container_name}-service',
                    pod_name=f'{data.container_name}-pod',
                    namespace_name=data.network_name,
                    publish_information=[
                        PublishInformationDataClass(
                            publish_port=pi.publish_port,
                            target_port=pi.target_port,
                            protocol=pi.protocol,
                        )
                        for pi in data.publish_information
                    ],
                    service_type=service_type
                ))
                final_container = service
            # create an ingress if exposure level is greater than ExposureLevel.CLUSTER_EXTERNAL
            if data.exposure_level.value > ExposureLevel.CLUSTER_EXTERNAL.value:
                ingress: dict = IngressManager.create(CreateIngressDataClass(
                    namespace_name=data.network_name,
                    ingress_name=f'{data.container_name}-ingress',
                    service_name=f'{data.container_name}-service',
                    host=config.HOST,
                    service_ports=service['service_ports']
                ))
                final_container = ingress

            id_key: str = [key for key in final_container.keys() if key.endswith('_id')][0]
            ip_key: str = [key for key in final_container.keys() if key.endswith('_ip')][0]
            name_key: str = [key for key in final_container.keys() if key.endswith('_name')][0]
            network_key: str = [key for key in final_container.keys() if key.endswith('_namespace')][0]
            ports_key: str = [key for key in final_container.keys() if key.endswith('_ports')][0]

            return {
                'container_id': final_container[id_key],
                'container_name': final_container[name_key],
                'container_ip': final_container[ip_key],
                'container_network': final_container[network_key],
                'container_ports': final_container[ports_key],
            }
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e

    @classmethod
    def delete(cls, data: DeleteContainerDataClass) -> None:
        '''
        Delete a container.
        Check the id of the container.
        Question: Why are we using ids instead of names? We can directly get resources using names.
        - We can have duplicate names, but not duplicate ids.
        - Imagine a pod and a service having the same name and you delete the pod instead of the service.
        
        INITIAL APPROACH:
        -----------------
        Deletion should be done in a heirarchical manner.
            - If we delete a pod, the service and ingress associated with it are useless. So we need to delete all of them.
            - If we delete a service, the ingress associated with it is useless. So we need to delete services. But the pod can still exist.
            - If we delete an ingress, the service and pod associated with it can still exist. So only delete ingress.
        In brief,
        - pod: Delete pod, associated service and associated ingress. Go up the heirarchy.
        - service: Delete service and associated ingress.
        - ingress: Delete ingress, associated services and associated pods.

        IMPROVEMENT:
        ------------
        1. A service can be associated to many pods. Not just a single pod. So its not fair to delete the service,
            just because we deleted one of the pods it was associated to. Same with ingress.
        2. So now, we delete pod or ingress or service.
        3. Then we delete all lingering resources. i.e. services with no pods associated, ingresses with no services associated.
        '''
        try:
            pod: dict | None = KubernetesContainerHelper.check_pod(
                namespace_name=data.network_name, container_id=data.container_id)
            if pod:
                PodManager.delete(DeletePodDataClass(
                    namespace_name=data.network_name,
                    pod_name=pod['pod_name'],
                ))

            service: dict | None = KubernetesContainerHelper.check_service(
                namespace_name=data.network_name, container_id=data.container_id)
            if service:
                ServiceManager.delete(DeleteServiceDataClass(
                    namespace_name=data.network_name,
                    service_name=service['service_name'],
                ))

            ingress: dict | None = KubernetesContainerHelper.check_ingress(
                namespace_name=data.network_name, container_id=data.container_id)
            if ingress:
                IngressManager.delete(DeleteIngressDataClass(
                    namespace_name=data.network_name,
                    ingress_name=ingress['ingress_name'],
                ))
            # delete lingering resources.
            KubernetesContainerHelper.delete_lingering_services(namespace_name=data.network_name)
            KubernetesContainerHelper.delete_lingering_ingresses(namespace_name=data.network_name)
        except ApiException as ae:
            raise ApiException(f'Error occurred while deleting container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e 


class DockerContainerManager(ContainerManager):
    pass
