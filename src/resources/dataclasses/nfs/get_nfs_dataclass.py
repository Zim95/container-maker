# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import GetResourceDataClass


@dataclass
class GetNFSDataClass(GetResourceDataClass):
    '''
    Get Pod Data Class
    '''
    namespace_name: str  # namespace of the pod
    nfs_name: str  # name of the nfs
