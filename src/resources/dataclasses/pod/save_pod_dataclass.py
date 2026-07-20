# built-ins
from dataclasses import dataclass, field

# modules
from src.resources.dataclasses import SaveResourceDataClass


@dataclass
class SavePodDataClass(SaveResourceDataClass):
    '''
    Save Pod DataClass
    '''
    pod_name: str  # The name of the pod
    namespace_name: str  # The namespace of the pod
    environment_variables: dict = field(default_factory=dict)  # Env vars for snapshot job
