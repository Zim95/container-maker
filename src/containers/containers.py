'''
Container Manager is the API for the container manager microservice.
If you want more control over the resources, use the resource manager.
Container Manager is restricted to do things a certain way.
There is no customizability.
'''

# builtins
import os
from collections import defaultdict

# modules
import src.common.config as config
from src.cloud_client import CloudClient, CloudClientError
from src.common.logging_setup import get_logger

# dataclasses
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.containers.dataclasses.list_container_dataclass import ListContainerDataClass
from src.containers.dataclasses.get_container_dataclass import GetContainerDataClass
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass

# resources
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass
from src.resources.dataclasses.ingress.create_ingress_dataclass import CreateIngressDataClass
from src.resources.dataclasses.ingress.delete_ingress_dataclass import DeleteIngressDataClass
from src.resources.dataclasses.ingress.get_ingress_dataclass import GetIngressDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.namespace.get_namespace_dataclass import GetNamespaceDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass, ResourceRequirementsDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass, PublishInformationDataClass, ServiceType
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager
from src.resources.ingress_manager import IngressManager
from src.containers import ContainerManager

# kubernetes
from kubernetes.client.exceptions import ApiException

logger = get_logger("containers")


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
    def _sanitize_name(cls, name: str) -> str:
        '''
        Mirror browseterm-server's sanitize_container_name so we can match a pod's `app` label:
        lowercase, spaces/underscores -> hyphens, drop anything that isn't [a-z0-9-].
        '''
        import re
        lowered: str = (name or '').strip().lower()
        hyphenated: str = lowered.replace(' ', '-').replace('_', '-')
        return re.sub(r'[^a-z0-9-]', '', hyphenated)

    @classmethod
    def _stored_pod_name(cls, container_row_data: dict) -> str | None:
        '''
        Pull the exact pod name recorded for this container in its DB row
        (associated_resources). This name is unique per pod (it carries a timestamp suffix),
        so it disambiguates even between two containers that share the same base name.
        '''
        import json
        resources = container_row_data.get('associated_resources') or []
        if isinstance(resources, str):
            try:
                resources = json.loads(resources)
            except Exception:
                resources = []
        for resource in resources:
            if isinstance(resource, dict) and resource.get('resource_type') == 'pod' and resource.get('resource_name'):
                return resource['resource_name']
        return None

    @classmethod
    def find_container_pod(cls, namespace_name: str, container_row_data: dict) -> dict | None:
        '''
        Resolve the live pod for a container WITHOUT trusting the historically unreliable
        kubernetes_id (pod uid). We anchor on the exact pod name stored in this container's own
        DB row (unique per pod). Only if that pod no longer exists (e.g. it was recreated) do we
        fall back to the stable `app` label -- and if the label matches more than one pod we
        refuse to guess rather than snapshot the wrong container.
        '''
        pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': namespace_name}))

        # Primary: exact, unique pod name recorded for this container.
        stored_pod_name: str | None = cls._stored_pod_name(container_row_data)
        if stored_pod_name:
            for pod in pods:
                if pod.get('pod_name') == stored_pod_name:
                    return pod

        # Fallback: stable `app` label (survives pod recreation, but not unique across
        # same-named containers -- so only use it when it maps to exactly one pod).
        sanitized: str = cls._sanitize_name(container_row_data.get('name'))
        label_matches: list = [p for p in pods if (p.get('pod_labels') or {}).get('app') == sanitized]
        if len(label_matches) == 1:
            return label_matches[0]
        if len(label_matches) > 1:
            raise Exception(
                f"Cannot uniquely resolve the pod for container id={container_row_data.get('id')} in "
                f"namespace={namespace_name}: stored pod name '{stored_pod_name}' was not found and "
                f"{len(label_matches)} pods share label app={sanitized}."
            )
        return None

    @classmethod
    def delete_pod(cls, namespace_name: str, pod_name: str) -> None:
        PodManager.delete(DeletePodDataClass(
            namespace_name=namespace_name,
            pod_name=pod_name,
        ))

    @classmethod
    def delete_service(cls, namespace_name: str, service_name: str) -> None:
        service: dict = ServiceManager.get(GetServiceDataClass(
            namespace_name=namespace_name,
            service_name=service_name,
        ))
        # FIX: Use 'associated_resources' instead of 'associated_pods'
        associated_pods: list = service.get('associated_resources', [])
        for pod in associated_pods:
            cls.delete_pod(namespace_name=namespace_name, pod_name=pod['pod_name'])
        ServiceManager.delete(DeleteServiceDataClass(
            namespace_name=namespace_name,
            service_name=service_name,
        ))

    @classmethod
    def delete_ingress(cls, namespace_name: str, ingress_name: str) -> None:
        ingress: dict = IngressManager.get(GetIngressDataClass(
            namespace_name=namespace_name,
            ingress_name=ingress_name,
        ))
        # FIX: Use 'associated_resources' instead of 'associated_services'
        associated_services: list = ingress.get('associated_resources', [])
        for service in associated_services:
            cls.delete_service(namespace_name=namespace_name, service_name=service['service_name'])
        IngressManager.delete(DeleteIngressDataClass(
            namespace_name=namespace_name,
            ingress_name=ingress_name,
        ))

    @classmethod
    def delete_lingering_namespaces(cls) -> None:
        '''
        Delete namespaces that have no resources associated with them.
        Skip protected namespaces.
        '''
        # System namespaces that should not be deleted.
        PROTECTED_NAMESPACES: list[str] = [
            'default', 
            'kube-system', 
            'kube-public', 
            'kube-node-lease',
            'ingress-nginx',
            'metallb-system',
        ]
        # for the rest, we just check if there are no pods, services or ingresses.
        namespaces: list = NamespaceManager.list()
        for ns in namespaces:
            namespace_name: str = ns['namespace_name']
            if namespace_name in PROTECTED_NAMESPACES:
                continue
            pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': namespace_name}))
            services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': namespace_name}))
            ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': namespace_name}))
            if not (pods or services or ingresses):
                NamespaceManager.delete(
                    DeleteNamespaceDataClass(namespace_name=namespace_name)
                )


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
        # if namespace does not exist return empty list
        namespace: dict = NamespaceManager.get(GetNamespaceDataClass(namespace_name=data.network_name))
        if not namespace:
            return []
        ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': data.network_name}))
        ingress_services: list = [service for ingress in ingresses for service in ingress.get('associated_resources', [])]
        ingress_pods: list = [pod for service in ingress_services for pod in service.get('associated_resources', [])]
        ingress_services_ids: list = [service['service_id'] for service in ingress_services]
        ingress_pods_ids: list = [pod['pod_id'] for pod in ingress_pods]

        services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': data.network_name}))
        unique_services: list = [service for service in services if service['service_id'] not in ingress_services_ids]
        unique_service_pods: list = [pod for service in unique_services for pod in service.get('associated_resources', [])]
        unique_service_pods_ids: list = [pod['pod_id'] for pod in unique_service_pods]

        pod_ids_to_exclude: list = ingress_pods_ids + unique_service_pods_ids

        pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': data.network_name}))
        unique_pods: list = [pod for pod in pods if pod['pod_id'] not in pod_ids_to_exclude]

        containers: list = []
        for ingress in ingresses:
            containers.append(
                {
                    'container_type': 'ingress',
                    'container_id': ingress['ingress_id'],
                    'container_name': ingress['ingress_name'],
                    'container_ip': ingress['ingress_ip'],
                    'container_network': ingress['ingress_namespace'],
                    'container_ports': ingress['ingress_ports'],
                    'container_associated_resources': ingress['associated_resources'],
                }
            )
        for service in unique_services:
            containers.append(
                {
                    'container_type': 'service',
                    'container_id': service['service_id'],
                    'container_name': service['service_name'],
                    'container_ip': service['service_ip'],
                    'container_network': service['service_namespace'],
                    'container_ports': service['service_ports'],
                    'container_associated_resources': service['associated_resources'],
                }
            )
        for pod in unique_pods:
            containers.append(
                {
                    'container_type': 'pod',
                    'container_id': pod['pod_id'],
                    'container_name': pod['pod_name'],
                    'container_ip': pod['pod_ip'],
                    'container_network': pod['pod_namespace'],
                    'container_ports': pod['pod_ports'],
                    'container_associated_resources': pod['associated_resources'],
                }
            )
        return containers

    @classmethod
    def get(cls, data: GetContainerDataClass) -> dict:
        '''
        Check if id of the container is pod, service or ingress.
        '''
        namespace: dict = NamespaceManager.get(GetNamespaceDataClass(namespace_name=data.network_name))
        if not namespace:
            return {}
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
            'container_type': final_container['resource_type'],
            'container_id': final_container[id_key],
            'container_name': final_container[name_key],
            'container_ip': final_container[ip_key],
            'container_network': final_container[network_key],
            'container_ports': final_container[ports_key],
            'container_associated_resources': final_container['associated_resources'],
        }

    @classmethod
    def save(cls, data: SaveContainerDataClass) -> list:
        '''
        Save a container.
        '''
        namespace: dict = NamespaceManager.get(GetNamespaceDataClass(namespace_name=data.network_name))
        if not namespace:
            return []

        # The gRPC request's container_id is the DATABASE id. The snapshot Job updates the DB row by
        # that DB id, so it is kept as the Job's CONTAINER_ID. But we must NOT trust the DB's
        # kubernetes_id (pod uid) to find the pod -- that value is historically unreliable (it can be
        # wrong from creation or stale after a pod is recreated). Instead resolve the live pod from
        # this container's own DB row (exact pod name, with a stable label as a fallback).
        cloud_client = CloudClient(config.BROWSETERM_CLOUD_API_URL, config.CLOUD_INTERNAL_API_TOKEN)
        container_row_data = cloud_client.get_container(data.container_id)
        if not container_row_data:
            raise Exception(f'Container not found in database: id={data.container_id}')

        pod: dict | None = KubernetesContainerHelper.find_container_pod(
            namespace_name=data.network_name, container_row_data=container_row_data
        )

        if pod:
            # Self-heal: refresh the DB's kubernetes_id to the pod's real current uid so other code
            # paths that still key on it behave correctly. Best-effort -- never fail the save on this.
            real_uid: str | None = pod.get('pod_id')
            if real_uid and container_row_data.get('kubernetes_id') != real_uid:
                try:
                    cloud_client.update_container(data.container_id, {"kubernetes_id": real_uid})
                except CloudClientError:
                    logger.warning("save(): could not self-heal kubernetes_id", extra={"container_id": data.container_id}, exc_info=True)

            # A pod gives a single dict; wrap it in a list to keep the output consistent.
            environment_variables = {
                "CONTAINER_ID": data.container_id,
            }
            return [PodManager.save(
                SavePodDataClass(
                    namespace_name=data.network_name,
                    pod_name=pod['pod_name'],
                    environment_variables=environment_variables,
                )
            )]

        # Not a bare pod: fall back to service / ingress exposed containers. These are resolved by
        # the stored kubernetes_id (legacy behaviour) and save all the pods they route to.
        kubernetes_id: str | None = container_row_data.get("kubernetes_id")
        service: dict | None = (
            KubernetesContainerHelper.check_service(namespace_name=data.network_name, container_id=kubernetes_id)
            if kubernetes_id else None
        )
        ingress: dict | None = (
            KubernetesContainerHelper.check_ingress(namespace_name=data.network_name, container_id=kubernetes_id)
            if kubernetes_id else None
        )

        if not (service or ingress):
            raise Exception(
                f'Cannot find a pod/service/ingress to snapshot for container id={data.container_id} '
                f'in namespace={data.network_name} (is it running?).'
            )

        if service:
            return ServiceManager.save_service_pods(GetServiceDataClass(
                namespace_name=data.network_name,
                service_name=service['service_name'],
            ))
        if ingress:
            return IngressManager.save_ingress_services(GetIngressDataClass(
                namespace_name=data.network_name,
                ingress_name=ingress['ingress_name'],
            ))

    @classmethod
    def validate_publish_information(cls, publish_information: list) -> None:
        '''
        Check for duplicate target and publish ports.
        We should not have duplicate target and publish ports.
        '''
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
            resource_requirements: ResourceRequirementsDataClass = ResourceRequirementsDataClass(
                cpu_request=data.resource_requirements.cpu_request,
                cpu_limit=data.resource_requirements.cpu_limit,
                memory_request=data.resource_requirements.memory_request,
                memory_limit=data.resource_requirements.memory_limit,
                ephemeral_request=data.resource_requirements.ephemeral_request,
                ephemeral_limit=data.resource_requirements.ephemeral_limit,
                snapshot_size_limit=data.resource_requirements.snapshot_size_limit,
            )
            # Add timestamp to pod name for uniqueness (prevents conflicts on quick recreate)
            from src.common.utils import generate_timestamp_suffix
            timestamp: str = generate_timestamp_suffix()
            pod: dict = PodManager.create(CreatePodDataClass(
                image_name=data.image_name,
                pod_name=f'{data.container_name}-pod-{timestamp}',
                container_name=data.container_name,  # Base name for labels (no timestamp)
                namespace_name=data.network_name,
                target_ports={pi.target_port for pi in data.publish_information},
                environment_variables=data.environment_variables,
                resource_requirements=resource_requirements,
            ))
            final_container = pod
            # create the service if exposure level is greater than ExposureLevel.INTERNAL
            if data.exposure_level.value > ExposureLevel.INTERNAL.value:
                service_type: ServiceType = (
                    ServiceType.LOAD_BALANCER if data.exposure_level.value > ExposureLevel.CLUSTER_LOCAL.value
                    else ServiceType.CLUSTER_IP
                )
                service: dict = ServiceManager.create(CreateServiceDataClass(
                    service_name=f'{data.container_name}-service-{timestamp}',
                    pod_label_selector=data.container_name,  # Use base name (no timestamp) for selector
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
                    ingress_name=f'{data.container_name}-ingress-{timestamp}',
                    service_name=f'{data.container_name}-service-{timestamp}',
                    host=config.INGRESS_HOST,
                    service_ports=service['service_ports']
                ))
                final_container = ingress

            id_key: str = [key for key in final_container.keys() if key.endswith('_id')][0]
            ip_key: str = [key for key in final_container.keys() if key.endswith('_ip')][0]
            name_key: str = [key for key in final_container.keys() if key.endswith('_name')][0]
            network_key: str = [key for key in final_container.keys() if key.endswith('_namespace')][0]
            ports_key: str = [key for key in final_container.keys() if key.endswith('_ports')][0]

            return {
                'container_type': final_container['resource_type'],
                'container_id': final_container[id_key],
                'container_name': final_container[name_key],
                'container_ip': final_container[ip_key],
                'container_network': final_container[network_key],
                'container_ports': final_container[ports_key],
                'container_associated_resources': final_container['associated_resources'],
            }
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e

    @classmethod
    def delete(cls, data: DeleteContainerDataClass) -> dict:
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

        ACTUAL APPROACH:
        ---------------
        1. For container manager, the collection of resources is a whole.
        2. A container that is exposed is a collection of ingress, service and pod.
        3. This means when the ingress container is deleted, all associated resources should also be deleted.
            Because the container is a whole, i.e. ingress + service + pod.
        4. We should however, delete the lingering resources if there are any, but as it is, thats how things should be.
        '''
        try:
            namespace: dict = NamespaceManager.get(GetNamespaceDataClass(namespace_name=data.network_name))
            if not namespace:
                return {'container_id': data.container_id, 'status': f'Network: {data.network_name} does not exist.'}
            pod: dict | None = KubernetesContainerHelper.check_pod(
                namespace_name=data.network_name, container_id=data.container_id)
            if pod:
                KubernetesContainerHelper.delete_pod(namespace_name=data.network_name, pod_name=pod['pod_name'])

            service: dict | None = KubernetesContainerHelper.check_service(
                namespace_name=data.network_name, container_id=data.container_id)
            if service:
                KubernetesContainerHelper.delete_service(
                    namespace_name=data.network_name, service_name=service['service_name'])

            ingress: dict | None = KubernetesContainerHelper.check_ingress(
                namespace_name=data.network_name, container_id=data.container_id)
            if ingress:
                KubernetesContainerHelper.delete_ingress(
                    namespace_name=data.network_name, ingress_name=ingress['ingress_name'])
            # delete lingering resources.
            KubernetesContainerHelper.delete_lingering_namespaces()
            return {'container_id': data.container_id, 'status': 'Deleted'}
        except ApiException as ae:
            raise ApiException(f'Error occurred while deleting container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e 


class DockerContainerManager(ContainerManager):
    pass
