 # builtins
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass


class ExposureLevel(Enum):
    INTERNAL: int = 1  # only pod
    CLUSTER_LOCAL: int = 2  # service with cluster ip
    CLUSTER_EXTERNAL: int = 3  # service with external ip
    EXPOSED: int = 4  # ingress level


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
    # Default limit is higher to accommodate full rootfs + snapshot tarball
    # in the shared EmptyDir volume without hitting disk exhaustion.
    ephemeral_limit: Optional[str] = '1Gi'
    # Snapshot volume size limit (per-pod EmptyDir; should be <= node capacity)
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
class CreateContainerDataClass:
    image_name: str  # name of the image to use
    container_name: str  # name of the container
    network_name: str  # name of the network
    exposure_level: ExposureLevel  # exposure level of the container
    publish_information: list[PublishInformationDataClass]  # list of publish information
    environment_variables: dict[str, str]  # environment variables
    resource_requirements: ResourceRequirementsDataClass = field(default_factory=ResourceRequirementsDataClass)  # Resource requirements for the container
