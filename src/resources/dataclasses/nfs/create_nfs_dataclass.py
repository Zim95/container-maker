# built-ins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import CreateResourceDataClass


@dataclass
class CreateNFSDataClass(CreateResourceDataClass):
    '''
    Create Pod DataClass
    '''
    nfs_name: str  # The name of the pod
    namespace_name: str  # The namespace of the pod
