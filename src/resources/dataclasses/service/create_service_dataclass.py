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
class CreateServiceDataClass(CreateResourceDataClass):
    '''
    Create Service DataClass
    '''
    service_name: str  # name of the service
    pod_name: str  # name of the pod
    namespace_name: str  # namespace of the pod
    service_port: int  # port of the service
    target_port: int  # port of the pod
    protocol: str  # protocol of the service
    service_type: Optional[ServiceType] = None  # type of the service. Default is LoadBalancer.
    node_port: Optional[int] = None  #  to hardcode the port for the service.
