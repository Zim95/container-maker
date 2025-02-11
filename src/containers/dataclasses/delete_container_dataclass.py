# builtins
from dataclasses import dataclass


@dataclass
class DeleteContainerDataClass:
    container_id: str  # id of the container to delete
    network_name: str  # network of the container to delete
