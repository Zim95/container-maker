# builtins
from abc import ABC, abstractmethod

# modules
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.containers.dataclasses.get_container_dataclass import GetContainerDataClass
from src.containers.dataclasses.list_container_dataclass import ListContainerDataClass


class ContainerManager(ABC):
    """
    Responsible for creating, deleting, listing and getting containers.
    """

    @classmethod
    @abstractmethod
    def list(cls, data: ListContainerDataClass) -> list[dict]:
        '''
        List all containers in a namespace.
        '''
        pass

    @classmethod
    @abstractmethod
    def get(cls, data: GetContainerDataClass) -> dict:
        '''
        Get a container.
        '''
        pass

    @classmethod
    @abstractmethod
    def create(cls, data: CreateContainerDataClass) -> dict:
        '''
        Create a container.
        '''
        pass

    @classmethod
    @abstractmethod
    def delete(cls, data: DeleteContainerDataClass) -> dict:
        '''
        Delete a container.
        '''
        pass
