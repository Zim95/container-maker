# built-ins
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
# modules
from src.resources.dataclasses import CreateResourceDataClass


class VolumeAccessMode(Enum):
    READ_WRITE_ONCE = 'ReadWriteOnce'
    READ_ONLY_MANY = 'ReadOnlyMany'
    READ_WRITE_MANY = 'ReadWriteMany'


class VolumeReclaimPolicy(Enum):
    DELETE = 'Delete'
    RETAIN = 'Retain'


@dataclass
class CreateVolumeDataClass(CreateResourceDataClass):
    '''
    Create Volume DataClass
    '''
    volume_name: str  # name of the volume
    namespace_name: str  # namespace to create the volume in
    host_path: str  # host path of the volume
    storage_size: str = '1Gi'  # size of the storage
    access_modes: List[VolumeAccessMode] = field(
        default_factory=lambda: [VolumeAccessMode.READ_WRITE_ONCE]
    )
    reclaim_policy: VolumeReclaimPolicy = VolumeReclaimPolicy.DELETE  # reclaim policy of the volume. Default is Delete.
