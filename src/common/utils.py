"""
Utility tools for the RestContainer.

Author: Namah Shrestha
"""

import os


def read_certs(env_var_key: str, path: str) -> str:
    """
    Read the certificates from environment.
    If not found read from path.
    Finally if not found we raise an error.

    Author: Namah Shrestha
    """
    try:
        cert = os.environ.get(env_var_key)
        if cert is not None:
            cert = cert.encode('utf-8')
        if cert is None:
            cert = open(path, 'rb').read()
        return cert
    except FileNotFoundError as fnfe:
        raise FileNotFoundError(fnfe)


def get_runtime_environment() -> str:
    """
    Get the runtime environment for the container.
    Right now, kubernetes and docker is supported.

    Reference: https://www.youtube.com/watch?v=mEQXXhniBQo

    Author: Namah Shrestha
    """
    if os.path.exists('./dockerenv'):
        return "docker"
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    return "unknown"
