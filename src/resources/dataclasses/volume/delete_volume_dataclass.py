# built-ins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import DeleteResourceDataClass


@dataclass
class DeleteVolumeDataClass(DeleteResourceDataClass):
    '''
    Delete Volume DataClass
    '''
    volume_name: str  # the name of the volume to delete
    namespace_name: str  # the namespace of the volume to delete
