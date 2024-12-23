# GRPC
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIServicer

# types
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import StartContainerRequest
from container_maker_spec.types_pb2 import StopContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import CreateContainerResponse
from container_maker_spec.types_pb2 import StartContainerResponse
from container_maker_spec.types_pb2 import StopContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerResponse

# modules
import src.handlers as handlers
import src.common.exceptions as exceptions

# third party
import grpc
import docker
import kubernetes.client.rest as k8s_rest

# TODO: Add some utilities classes for common functionalities here.

class ContainerMakerAPIServicerImpl(ContainerMakerAPIServicer):
    """
    Container Maker GRPC API Servicer.

    - Create, Start, Stop and Delete Containers.

    Author: Namah Shrestha
    """

    def createContainer(self, request: CreateContainerRequest, context: grpc.ServicerContext) -> CreateContainerResponse:
        try:
            """
            Create container request.

            Author: Namah Shrestha
            """
            handler: handlers.Handler = handlers.CreateContainerHandler(request)
            return handler.handle()
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

    def startContainer(self, request, context):
        raise Exception("Test Exception")

    def stopContainer(self, request, context):
        return StopContainerResponse()

    def deleteContainer(self, request, context):
        return DeleteContainerResponse()
