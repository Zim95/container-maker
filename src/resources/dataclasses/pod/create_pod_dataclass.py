 # built-ins
from dataclasses import dataclass, field
from typing import Dict, Set, Optional

# modules
from src.resources.dataclasses import CreateResourceDataClass


@dataclass
class ResourceRequirementsDataClass:
    '''
    Resource Requirements DataClass
    '''
    # CPU (1 CPU max, conservative request)
    cpu_request: Optional[str] = '100m'     # 0.1 CPU requested
    cpu_limit: Optional[str] = '1'         # 1 CPU limit
    # Memory (1Gi max, conservative request)
    memory_request: Optional[str] = '256Mi'
    memory_limit: Optional[str] = '1Gi'
    # Ephemeral storage
    ephemeral_request: Optional[str] = '512Mi'
    ephemeral_limit: Optional[str] = '1Gi'
    # Snapshot volume size limit
    snapshot_size_limit: Optional[str] = '2Gi'

    def to_dict(self) -> dict:
        '''
        Convert the ResourceRequirementsDataClass to a dictionary
        '''
        return {
            'cpu_request': self.cpu_request,
            'cpu_limit': self.cpu_limit,
            'memory_request': self.memory_request,
            'memory_limit': self.memory_limit,
            'ephemeral_request': self.ephemeral_request,
            'ephemeral_limit': self.ephemeral_limit,
            'snapshot_size_limit': self.snapshot_size_limit,
        }


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
    resource_requirements: ResourceRequirementsDataClass = field(default_factory=ResourceRequirementsDataClass)  # Resource requirements for the pod
