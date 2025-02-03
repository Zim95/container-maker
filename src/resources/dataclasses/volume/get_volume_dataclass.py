# built-ins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import GetResourceDataClass


@dataclass
class GetVolumeDataClass(GetResourceDataClass):
    '''
    Get Volume DataClass
    '''
    namespace_name: str  # namespace to get volume in
    volume_name: str  # name of the volume to get
