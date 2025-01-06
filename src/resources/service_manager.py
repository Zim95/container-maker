# modules
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.resource_manager import KubernetesResourceManager
from src.common.exceptions import UnsupportedRuntimeEnvironment

# third party
from kubernetes.client.rest import ApiException
from kubernetes.client import V1Service


class ServiceManager(KubernetesResourceManager):
    '''
    Manage kubernetes services.
    '''

    @classmethod
    def list(cls, data: ListServiceDataClass) -> list[dict]:
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
    def create(cls, data: CreateServiceDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            # Implementation will go here
            pass
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