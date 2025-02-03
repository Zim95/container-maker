# built-ins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import ListResourceDataClass


@dataclass
class ListVolumeDataClass(ListResourceDataClass):
    '''
    List Volume DataClass
    '''
    namespace_name: str  # namespace to list volumes in
