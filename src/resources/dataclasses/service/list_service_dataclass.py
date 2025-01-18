# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import ListResourceDataClass


@dataclass
class ListServiceDataClass(ListResourceDataClass):
    '''
    List Service DataClass
    '''
    namespace_name: str
