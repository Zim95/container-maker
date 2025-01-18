# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import GetResourceDataClass


@dataclass
class GetNamespaceDataClass(GetResourceDataClass):
    '''
    Get Namespace DataClass
    '''
    namespace_name: str