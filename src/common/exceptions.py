class UnsupportedRuntimeEnvironment(Exception):
    """
    When there is a mismatch between the runtime environment and the resource manager used.
    For example, using a Kubernetes resource manager on a Docker runtime environment.
    """
    pass


class ResourceManagerNotFound(Exception):
    """
    When resource manager for the runtime environment is not found.
    """
    pass
