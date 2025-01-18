# builtins
from abc import abstractmethod

# modules
from src.resources.dataclasses import GetResourceDataClass, ListResourceDataClass
from src.resources.dataclasses import CreateResourceDataClass
from src.resources.dataclasses import StartResourceDataClass
from src.resources.dataclasses import StopResourceDataClass
from src.resources.dataclasses import DeleteResourceDataClass
from src.resources.utils import get_runtime_environment
from src.common.exceptions import UnsupportedRuntimeEnvironment

# third party
from kubernetes.client import CoreV1Api
from kubernetes.config import load_incluster_config


class ResourceManager:
    """
    Base ResourceManager Abstract Class.
    Contains a blueprint of methods that can be used to manage a resource.
    Operations: Create, Start, Stop and Delete resources.
    """

    @classmethod
    @abstractmethod
    def list(cls, data: ListResourceDataClass) -> list[dict]:
        """
        List Resources
        :params:
            :data: ListResourceDataClass
        :returns: list[dict]: List of resources
        """
        raise NotImplementedError(f'{cls.__name__}.list: Is not implemented for this resource.')

    @classmethod
    @abstractmethod
    def get(cls, data: GetResourceDataClass) -> dict:
        """
        Get a resource.
        :params:
            :data: GetResourceDataClass
        :returns: dict: Info of resource
        """
        raise NotImplementedError(f'{cls.__name__}.get: Is not implemented for this resource.')

    @classmethod
    @abstractmethod
    def create(cls, data: CreateResourceDataClass) -> dict:
        """
        Create a resource.
        :params:
            :data: CreateResourceDataClass
        :returns: dict: Info of created resource
        """
        raise NotImplementedError(f'{cls.__name__}.create: Is not implemented for this resource.')

    @classmethod
    @abstractmethod
    def start(cls, data: StartResourceDataClass) -> dict:
        """
        Start a resource.
        :params:
            :data: StartResourceDataClass
        :returns: dict: Info of started resource
        """
        raise NotImplementedError(f'{cls.__name__}.start: Is not implemented for this resource.')

    @classmethod
    @abstractmethod
    def stop(cls, data: StopResourceDataClass) -> dict:
        """
        Stop a resource.
        :params:
            :data: StopResourceDataClass
        :returns: dict: Info of stopped resource
        """
        raise NotImplementedError(f'{cls.__name__}.stop: Is not implemented for this resource.')

    @classmethod
    @abstractmethod
    def delete(cls, data: DeleteResourceDataClass) -> dict:
        """
        Delete a resource.
        :params:
            :data: DeleteResourceDataClass
        :returns: dict: Info of deleted resource
        """
        raise NotImplementedError(f'{cls.__name__}.delete: Is not implemented for this resource.')


class KubernetesResourceManager(ResourceManager):
    """
    Kubernetes Resource Manager
    """
    client: CoreV1Api | None = None
    if get_runtime_environment() == 'kubernetes':
        load_incluster_config()
        client = CoreV1Api()

    @classmethod
    def check_kubernetes_client(cls) -> None:
        '''
        Check if the client exists or not.
        If not raise Error.
        :params: None
        :returns: None
        '''
        if cls.client is None:
            client_is_none: str = (
                f"The code is not running on Kubernetes. {cls.__name__} is only implemented for Kubernetes."
            )
            raise UnsupportedRuntimeEnvironment(client_is_none)
