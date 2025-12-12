from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer, transform_container_response

# GRPC Data types
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import ListContainerResponse

# Container Maker Data types
from src.containers.dataclasses.list_container_dataclass import ListContainerDataClass


class ListContainerInputDataTransformer(InputDataTransformer):
    @classmethod
    def transform(cls, input_data: ListContainerRequest) -> ListContainerDataClass:
        return ListContainerDataClass(
            network_name=input_data.network_name
        )


class ListContainerOutputDataTransformer(OutputDataTransformer):
    @classmethod
    def transform(cls, input_data: list[dict]) -> ListContainerResponse:
        return ListContainerResponse(
            containers=[
                transform_container_response(container)
                for container in input_data
            ]
        )
