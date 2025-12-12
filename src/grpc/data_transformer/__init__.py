from google.protobuf.message import Message
from typing import TypeVar
from abc import ABC, abstractmethod
from dataclasses import dataclass

from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PortInformation
from container_maker_spec.types_pb2 import AssociatedResource
from container_maker_spec.types_pb2 import ContainerResources


T = TypeVar('T', bound=dataclass)


class InputDataTransformer(ABC):
    '''
    Transform protobuf message to dataclass
    '''
    @classmethod
    @abstractmethod
    def transform(cls, input_data: Message) -> T:
        '''
        Transform protobuf message to dataclass
        '''
        pass


class OutputDataTransformer(ABC):
    '''
    Transform dictionary to protobuf message
    '''
    @classmethod
    @abstractmethod
    def transform(cls, output_data: dict | list[dict]) -> Message:
        '''
        Transform dictionary to protobuf message
        '''
        pass


def transform_resources(resources_dict: dict) -> ContainerResources:
    """Transform a resources dict to ContainerResources proto message."""
    return ContainerResources(
        cpu_request=resources_dict.get('cpu_request', ''),
        cpu_limit=resources_dict.get('cpu_limit', ''),
        memory_request=resources_dict.get('memory_request', ''),
        memory_limit=resources_dict.get('memory_limit', ''),
        ephemeral_request=resources_dict.get('ephemeral_request', ''),
        ephemeral_limit=resources_dict.get('ephemeral_limit', ''),
        snapshot_size_limit=resources_dict.get('snapshot_size_limit', ''),
    )


def get_resource_name(resource_dict: dict) -> str:
    """
    Extract the resource name from a resource dict based on resource_type.
    The name key is prefixed with the resource type (e.g., 'service_name', 'pod_name', 'container_name').
    """
    resource_type = resource_dict.get('resource_type', '')
    # Map resource_type to the corresponding name key prefix
    prefix_map = {
        'service': 'service_name',
        'pod': 'pod_name',
        'pod_container': 'container_name',
        'ingress': 'ingress_name',
    }
    name_key = prefix_map.get(resource_type, 'resource_name')
    return resource_dict.get(name_key, '')


def transform_associated_resource(resource_dict: dict) -> AssociatedResource:
    """Recursively transform associated resource dict to proto message."""
    container_resources = None
    if 'container_resources' in resource_dict:
        container_resources = transform_resources(resource_dict['container_resources'])

    nested_resources = []
    if 'associated_resources' in resource_dict:
        nested_resources = [
            transform_associated_resource(nested)
            for nested in resource_dict['associated_resources']
        ]

    return AssociatedResource(
        resource_name=get_resource_name(resource_dict),
        resource_type=resource_dict.get('resource_type', ''),
        container_resources=container_resources,
        associated_resources=nested_resources,
    )


def transform_container_response(input_data: dict) -> ContainerResponse:
    """Transform a container dict to ContainerResponse proto message."""
    associated_resources = []
    if 'container_associated_resources' in input_data:
        associated_resources = [
            transform_associated_resource(resource)
            for resource in input_data['container_associated_resources']
        ]

    return ContainerResponse(
        container_id=input_data['container_id'],
        container_name=input_data['container_name'],
        container_ip=input_data['container_ip'],
        container_network=input_data['container_network'],
        ports=[PortInformation(
            name=port['name'],
            container_port=port['container_port'],
            protocol=port['protocol'],
        ) for port in input_data['container_ports']],
        associated_resources=associated_resources,
    )
