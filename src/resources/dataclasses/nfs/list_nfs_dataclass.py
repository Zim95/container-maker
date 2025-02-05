# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import ListResourceDataClass


@dataclass
class ListNFSDataClass(ListResourceDataClass):
    '''
    List Pod Data Class
    '''
    namespace_name: str  # namespace of the pod
