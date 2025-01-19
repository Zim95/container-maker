# builtins
from dataclasses import dataclass
# from typing import Dict List

# modules
from src.resources.dataclasses import CreateResourceDataClass

@dataclass
class CreateServiceDataClass(CreateResourceDataClass):
    '''
    Create Service DataClass
    '''
    service_name: str  # name of the service
    pod_name: str  # name of the pod
    namespace_name: str  # namespace of the pod
    service_port: int  # port of the service
    target_port: int  # port of the pod
    protocol: str  # protocol of the service
