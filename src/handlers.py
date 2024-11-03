# builtins
import abc
import typing

# modules
import src.exceptions as exceptions
import src.constants as constants
import src.containers as containers
import src.utils as utils
import src.message_brokers as mb

# third party
import docker
import kubernetes.client.rest as k8s_rest


class Handler:
    """
    Handler abstract class. Receives request data.
    Has a handle method which is an abstract class method.

    Author: Namah Shrestha
    """

    def __init__(self, request: typing.Any) -> None:
        """
        Initialize the request.

        Author: Namah Shrestha
        """
        self.request: typing.Any = request

    @abc.abstractclassmethod
    def handle(self) -> dict | None:
        """
        Abstract handle logic to be implemented by child classes.

        Author: Namah Shrestha
        """
        pass


class ContainerHandler(Handler):
    """
    Base container handler. Will parse the required data.

    Author: Namah Shrestha
    """

    def __init__(self, request: typing.Any) -> None:
        """
        Initialize request parameters. Call super.__init__

        Author: Namah Shrestha
        """
        super().__init__(request)

    def handle(self) -> dict | None:
        """
        Get runtime environment. Based on that choose the container manager.
        Handle container manager exception and unsupported runtime environment exception.

        This functionality is specific to containers and therefore is only defined in
        Container handler.
        Other handlers may not need to know the runtime environment.

        Author: Namah Shrestha
        """
        runtime_environment: str = utils.get_runtime_environment()
        if runtime_environment not in constants.SUPPORTED_ENVIRONMENTS:
            runtime_environment_not_supported: str = (
                "Unsupported runtime environment: "
                f"{runtime_environment}"
            )
            exceptions.UnsupportedRuntimeEnvironment(
                runtime_environment_not_supported
            )

        self.container_manager: containers.ContainerManager = \
                containers.ENV_CONTAINER_MGR_MAPPING.get(
                    runtime_environment)
        if not self.container_manager:
            cnmgrnf: str = (
                f"Container Manager for {runtime_environment}"
                "has not been assigned yet. We regret the inconvenience."
            )
            raise exceptions.ContainerManagerNotFound(cnmgrnf)


class CreateContainerHandler(ContainerHandler):
    """
    Handler to create containers in either docker or kubernetes.

    Author: Namah Shrestha
    """

    def __init__(self, request: typing.Any) -> None:
        """
        Initialize request parameters. Call super.__init__

        Author: Namah Shrestha
        """
        super().__init__(request)
    
    def handle(self) -> typing.Any:
        """
        Parse the request payload.
        Extract:
            image_name: str: Name of the image.
            container_name: str: Name of the container.
            container_network: str: Name of the network.
            publish_information: dict: Port mappings.
            environment: Environment dictionary.
        Create the container based on these params.

        Author: Namah Shrestha
        """
        try:
            super().handle()
            message_broker: mb.MessageBroker = mb.CreateContainerMessageBroker(self.request)
            container_payload: dict = message_broker.parse_request()
            container_manager_object: containers.ContainerManager = \
                self.container_manager(
                    image_name=container_payload.get("image_name", ""),
                    container_name=container_payload.get("container_name", ""),
                    container_network=container_payload.get("container_network", ""),
                    publish_information=container_payload.get("publish_information", {}),
                    environment=container_payload.get("environment", {}),
                )
            response: list[dict] = container_manager_object.create_container()
            return message_broker.make_response(response)
        except exceptions.UnsupportedRuntimeEnvironment as e:
            raise exceptions.UnsupportedRuntimeEnvironment(e)
        except exceptions.ContainerManagerNotFound as e:
            raise exceptions.ContainerManagerNotFound(e)
        except docker.errors.DockerException as de:
            raise docker.errors.DockerException(de)
        except k8s_rest.ApiException as ka:
            raise k8s_rest.ApiException(ka)
        except exceptions.ContainerClientNotResolved as ccnr:
            raise exceptions.ContainerClientNotResolved(ccnr)
        except Exception as e:
            raise Exception(e)
