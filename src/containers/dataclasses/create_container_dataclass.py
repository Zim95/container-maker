# builtins
from dataclasses import dataclass
from enum import Enum

from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass


class ExposureLevel(Enum):
    INTERNAL: int = 1  # only pod
    CLUSTER_LOCAL: int = 2  # service with cluster ip
    CLUSTER_EXTERNAL: int = 3  # service with external ip
    EXPOSED: int = 4  # ingress level


@dataclass
class CreateContainerDataClass:
    image_name: str  # name of the image to use
    container_name: str  # name of the container
    network_name: str  # name of the network
    exposure_level: ExposureLevel  # exposure level of the container
    publish_information: list[PublishInformationDataClass]  # list of publish information
    environment_variables: dict[str, str]  # environment variables
