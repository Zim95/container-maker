# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import CreateResourceDataClass


@dataclass
class CreateIngressDataClass(CreateResourceDataClass):
    '''
    Create Ingress Dataclass
    '''
    ingress_name: str  # name of the ingress to create
    namespace_name: str  # namespace to create ingress on
    service_name: str  # name of the service to create ingress on
    host: str  # host to create ingress on
    service_ports: list[dict]  # list of service ports to create ingress on
