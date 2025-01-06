# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import DeleteResourceDataClass


@dataclass
class DeletePodDataClass(DeleteResourceDataClass):
    '''
    Delete Pod Data Class
    '''
    namespace_name: str  # namespace of the pod
    pod_name: str  # name of the pod
