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
