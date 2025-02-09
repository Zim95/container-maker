# builtins
import os

HOST: str = os.getenv('HOST', 'localhost')
NFS_IP: str = os.getenv('NFS_IP', None)
NFS_PATH: str = os.getenv('NFS_PATH', None)
