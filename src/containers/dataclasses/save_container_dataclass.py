# builtins
from dataclasses import dataclass


@dataclass
class SaveContainerDataClass:
    container_id: str  # container id (kubernetes) / container id (docker)
    network_name: str  # namespace name (kubernetes) / network name (docker)
    # Database credentials for snapshot job
    db_host: str = ""
    db_port: int = 5432
    db_username: str = ""
    db_password: str = ""
    db_database: str = ""