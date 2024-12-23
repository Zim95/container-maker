# builtins
import abc
import typing

# modules
from container_maker_spec.types_pb2 import CreateContainerResponseItem, CreateContainerResponse


class MessageBroker:
    """
    Receives GRPC Request and turns it to a dictionary.
    Formats a GRPC Response and returns it.

    Author: Namah Shrestha
    """
    def __init__(self, request: typing.Any) -> None:
        """
        Recieve Request and store it.
        :params:
            :request: grpc request: The grpc request
        :returns: None

        Author: Namah Shrestha
        """
        self.request = request

    @abc.abstractclassmethod
    def parse_request(self) -> dict:
        """
        Parse the grpc request and return the dictionary.
        :params: None
        :returns: dict: The dictionary version of the grpc request.

        Author: Namah Shrestha
        """
        pass

    @abc.abstractclassmethod
    def make_response(self, response: dict) -> typing.Any:
        """
        Make the GRPC response out of the response dictionary.
        :params:
            :response: dict: The response dictionary.
        :returns: any: Grpc Message.

        Author: Namah Shrestha
        """
        pass


class CreateContainerMessageBroker(MessageBroker):
    """
    Create Container Message Broker.

    Author: Namah Shrestha
    """
    def __init__(self, request: typing.Any) -> None:
        super().__init__(request)

    def parse_request(self) -> dict:
        return {
            "image_name": request.image_name,
            "container_name": request.container_name,
            "container_network": request.container_network,
            "publish_information": request.publish_information,
            "environment": request.environment,
        }

    def make_response(self, response: list[dict]) -> typing.Any:
        create_container_response_items: list = list(map(
            lambda response: CreateContainerResponseItem(
                container_id=response["container_id"],
                container_image=response["image_name"],
                container_name=response["container_name"],
                container_network=response["container_network"],
                container_port=response["container_port"]
            ),
            response
        ))
        create_container_response: CreateContainerResponse = CreateContainerResponse(create_container_response_items)
        return create_container_response
