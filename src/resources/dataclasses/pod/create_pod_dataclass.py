# builtins
from dataclasses import dataclass

# modules
from src.resources.dataclasses import CreateResourceDataClass


@dataclass
class CreatePodDataClass(CreateResourceDataClass):
    '''
    Create Pod DataClass
    '''
    image_name: str  # The name of the image
    pod_name: str  # The name of the pod
    namespace_name: str  # The namespace of the pod
    target_ports: set # a set of target ports for the pod
    environment_variables: dict  # Environment variables for the pod
