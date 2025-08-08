# GRPC
from container_maker_spec.service_pb2_grpc import ContainerMakerAPIServicer

# types
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import ListContainerResponse
from container_maker_spec.types_pb2 import DeleteContainerResponse
from container_maker_spec.types_pb2 import SaveContainerRequest
from container_maker_spec.types_pb2 import SaveContainerResponse

# modules
from src.common.exceptions import UnsupportedRuntimeEnvironment

# third party
from grpc import ServicerContext
from kubernetes.client.rest import ApiException

# data transformers
from src.grpc.data_transformer.create_container_transformer import CreateContainerInputDataTransformer
from src.grpc.data_transformer.create_container_transformer import CreateContainerOutputDataTransformer
from src.grpc.data_transformer.list_container_transformer import ListContainerInputDataTransformer
from src.grpc.data_transformer.list_container_transformer import ListContainerOutputDataTransformer
from src.grpc.data_transformer.get_container_transformer import GetContainerInputDataTransformer
from src.grpc.data_transformer.get_container_transformer import GetContainerOutputDataTransformer
from src.grpc.data_transformer.delete_container_transformer import DeleteContainerInputDataTransformer
from src.grpc.data_transformer.delete_container_transformer import DeleteContainerOutputDataTransformer
from src.grpc.data_transformer.save_container_transformer import SaveContainerInputDataTransformer
from src.grpc.data_transformer.save_container_transformer import SaveContainerOutputDataTransformer

# dataclasses
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass
from src.containers.dataclasses.list_container_dataclass import ListContainerDataClass
from src.containers.dataclasses.get_container_dataclass import GetContainerDataClass
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass

# containers
from src.containers.containers import KubernetesContainerManager


class ContainerMakerAPIServicerImpl(ContainerMakerAPIServicer):
    """
    Container Maker GRPC API Servicer.

    - Create, List, Get and Delete Containers.
    """

    def createContainer(self, request: CreateContainerRequest, context: ServicerContext) -> ContainerResponse:
        try:
            input_data: CreateContainerDataClass = CreateContainerInputDataTransformer.transform(request)
            container: dict = KubernetesContainerManager.create(input_data)
            output_data: ContainerResponse = CreateContainerOutputDataTransformer.transform(container)
            return output_data
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e

    def listContainer(self, request: ListContainerRequest, context: ServicerContext) -> ListContainerResponse:
        try:
            input_data: ListContainerDataClass = ListContainerInputDataTransformer.transform(request)
            containers: list[dict] = KubernetesContainerManager.list(input_data)
            output_data: ListContainerResponse = ListContainerOutputDataTransformer.transform(containers)
            return output_data
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occurred while listing containers: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e

    def getContainer(self, request: GetContainerRequest, context: ServicerContext) -> ContainerResponse:
        try:
            input_data: GetContainerDataClass = GetContainerInputDataTransformer.transform(request)
            container: dict = KubernetesContainerManager.get(input_data)
            output_data: ContainerResponse = GetContainerOutputDataTransformer.transform(container)
            return output_data
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occurred while getting container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e

    def deleteContainer(self, request: DeleteContainerRequest, context: ServicerContext) -> DeleteContainerResponse:
        try:
            input_data: DeleteContainerDataClass = DeleteContainerInputDataTransformer.transform(request)
            container: dict = KubernetesContainerManager.delete(input_data)
            output_data: DeleteContainerResponse = DeleteContainerOutputDataTransformer.transform(container)
            return output_data
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occurred while deleting container: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occurred: {str(e)}') from e

    def saveContainer(self, request: SaveContainerRequest, context: ServicerContext) -> SaveContainerResponse:
        try:
            input_data: SaveContainerDataClass = SaveContainerInputDataTransformer.transform(request)
            container: dict = KubernetesContainerManager.save(input_data)
            output_data: SaveContainerResponse = SaveContainerOutputDataTransformer.transform(container)
            return output_data
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occurred while saving container: {str(ae)}') from ae
