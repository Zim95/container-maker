# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import ListResourceDataClass


@dataclass
class ListIngressDataClass(ListResourceDataClass):
    '''
    List Ingress Dataclass
    '''
    namespace_name: str  # The namespace to list ingress from.
