# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import GetResourceDataClass


@dataclass
class GetServiceDataClass(GetResourceDataClass):
    '''
    Get Service DataClass
    '''
    namespace_name: str  # namespace of the service
    service_name: str  # name of the service
