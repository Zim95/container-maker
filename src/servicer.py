# GRPC
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIServicer

# types
from container_maker_spec.types_pb2 import CreateContainerResponse
from container_maker_spec.types_pb2 import StartContainerResponse
from container_maker_spec.types_pb2 import StopContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerResponse


class ContainerMakerAPIServicerImpl(ContainerMakerAPIServicer):

    def createContainer(self, request, context):
        return CreateContainerResponse()

    def startContainer(self, request, context):
        return StartContainerResponse()

    def stopContainer(self, request, context):
        return StopContainerResponse()

    def deleteContainer(self, request, context):
        return DeleteContainerResponse()
