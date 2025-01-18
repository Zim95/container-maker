# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import DeleteResourceDataClass


@dataclass
class DeleteNamespaceDataClass(DeleteResourceDataClass):
    '''
    Delete Namespace DataClass
    '''
    namespace_name: str  # name of the namespace.

