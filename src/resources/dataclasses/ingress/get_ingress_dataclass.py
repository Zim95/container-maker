# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import GetResourceDataClass


@dataclass
class GetIngressDataClass(GetResourceDataClass):
    '''
    Get Ingress Dataclass
    '''
    namespace_name: str  # The namespace to get ingress from.
    ingress_name: str  # The ingress to get.
