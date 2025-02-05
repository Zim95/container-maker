# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import DeleteResourceDataClass


@dataclass
class DeleteNFSDataClass(DeleteResourceDataClass):
    '''
    Delete Pod Data Class
    '''
    namespace_name: str  # namespace of the pod
    nfs_name: str  # name of the pod
