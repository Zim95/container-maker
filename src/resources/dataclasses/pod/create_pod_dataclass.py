# built-ins
from dataclasses import dataclass, field
from typing import Optional, Dict, Set

# modules
from src.resources.dataclasses import CreateResourceDataClass


@dataclass
class CreatePodDataClass(CreateResourceDataClass):
    '''
    Create Pod DataClass
    '''
    pod_name: str  # The name of the pod
    namespace_name: str  # The namespace of the pod
    image_name: str  # The name of the image
    target_ports: Set[int] = field(default_factory=set)  # Set of target ports for the pod
    environment_variables: Dict[str, str] = field(default_factory=dict)  # Environment variables for the pod
    volume_config: Optional[Dict] = field(default_factory=dict)  # Volume data for the pod
