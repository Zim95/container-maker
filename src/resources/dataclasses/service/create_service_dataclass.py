# builtins
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# modules
from src.resources.dataclasses import CreateResourceDataClass


class ServiceType(Enum):
    NODE_PORT = 'NodePort'
    LOAD_BALANCER = 'LoadBalancer'
    CLUSTER_IP = 'ClusterIP'


@dataclass
class PublishInformationDataClass:
    publish_port: int  # the port of the service
    target_port: int  # the port of the pod
    protocol: str  # the protocol of the service
    node_port: Optional[int] = None  # the node port of the service. The service type must be NodePort to use this.


@dataclass
class CreateServiceDataClass(CreateResourceDataClass):
    '''
    Create Service DataClass
    '''
    service_name: str  # name of the service
    pod_name: str  # name of the pod
    namespace_name: str  # namespace of the pod
    publish_information: list[PublishInformationDataClass]  # list of publish information
    service_type: Optional[ServiceType] = None  # type of the service. Default is LoadBalancer.
    node_port: Optional[int] = None  #  to hardcode the port for the service.
