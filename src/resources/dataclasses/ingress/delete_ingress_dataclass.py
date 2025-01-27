# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import DeleteResourceDataClass


@dataclass
class DeleteIngressDataClass(DeleteResourceDataClass):
    '''
    Delete Ingress Dataclass
    '''
    namespace_name: str  # The namespace to delete ingress from.
    ingress_name: str  # The ingress to delete.
