# builtins
from dataclasses import dataclass


@dataclass
class SaveContainerDataClass:
    container_id: str  # container id (kubernetes) / container id (docker)
    network_name: str  # namespace name (kubernetes) / network name (docker)