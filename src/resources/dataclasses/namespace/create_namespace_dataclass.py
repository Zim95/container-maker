# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import CreateResourceDataClass


@dataclass
class CreateNamespaceDataClass(CreateResourceDataClass):
    '''
    Create Namespace DataClass
    '''
    namespace_name: str  # name of the namespace.
