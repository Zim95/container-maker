# GRPC
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIServicer

# types
from container_maker_spec.types_pb2 import CreateContainerResponse, CreateContainerResponseItem
from container_maker_spec.types_pb2 import StartContainerResponse
from container_maker_spec.types_pb2 import StopContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerResponse


class ContainerMakerAPIServicerImpl(ContainerMakerAPIServicer):

    def createContainer(self, request, context):
        try:
            create_container_response_item = CreateContainerResponseItem(
                container_id="test_id",
                container_image=request.image_name,
                container_name=request.container_name,
                container_network=request.container_network,
                container_port=5
            )
            response: CreateContainerResponse = CreateContainerResponse()
            response.create_container_response_item.extend([create_container_response_item])
            return response
        except Exception as e:
            raise Exception(e.details())

    def startContainer(self, request, context):
        raise Exception("Test Exception")

    def stopContainer(self, request, context):
        return StopContainerResponse()

    def deleteContainer(self, request, context):
        return DeleteContainerResponse()
