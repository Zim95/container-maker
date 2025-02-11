# builtins
from dataclasses import dataclass


@dataclass
class ListContainerDataClass:
    network_name: str  # namespace name (kubernetes) / network name (docker)
