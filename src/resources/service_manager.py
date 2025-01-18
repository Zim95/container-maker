# modules
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.resource_manager import KubernetesResourceManager
from src.common.exceptions import UnsupportedRuntimeEnvironment

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
    def list(cls, data: ListServiceDataClass) -> list[V1Service]:
        try:
            cls.check_kubernetes_client()
            return cls.client.list_namespaced_service(namespace=data.namespace_name).items
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
            return cls.client.read_namespaced_service(name=data.service_name, namespace=data.namespace_name)
        except ApiException as ae:
            raise ApiException(f'Error occured while getting service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def create(cls, data: CreateServiceDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            # check for existing services
            service_list: list[V1Service] = cls.list(ListServiceDataClass(**{'namespace_name': data.namespace_name}))
            service_name_info_map: dict = {
                service.metadata.name: {
                    "service_id": service.metadata.uid,
                    "service_ip": service._spec.cluster_ip,
                    "service_name": service.metadata.name,
                    "service_namespace": data.namespace_name,
                    "service_port": data.service_port,
                }
                for service in service_list
            }
            # return existing service if it exists
            if service_name_info_map.get(data.service_name, {}):
                return service_name_info_map[data.service_name]

            # create the service manifest
            service_manifest: V1Service = V1Service(
                metadata=V1ObjectMeta(name=data.service_name),
                spec=V1ServiceSpec(
                    selector={"app": data.pod_name},
                    ports=[
                        V1ServicePort(
                            port=data.service_port,
                            target_port=data.target_port,
                            protocol=data.protocol,
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
                "service_ip": service._spec.cluster_ip,
                "service_name": service.metadata.name,
                "service_namespace": data.namespace_name,
                "service_port": data.service_port,
            }
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def delete(cls, data: DeleteServiceDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            cls.client.delete_namespaced_service(data.service_name, data.namespace_name)
            return {'status': 'success'}
        except ApiException as ae:
            raise ApiException(f'Error occurred while deleting service: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e 
