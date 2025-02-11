# builtins
from dataclasses import dataclass


@dataclass
class GetContainerDataClass:
    container_id: str  # namespace id (kubernetes) / container id (docker)
    network_name: str  # namespace name (kubernetes) / network name (docker)
