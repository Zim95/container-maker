from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer, transform_container_response

# GRPC Data types
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse

# Container Maker Data types
from src.containers.dataclasses.get_container_dataclass import GetContainerDataClass


class GetContainerInputDataTransformer(InputDataTransformer):
    @classmethod
    def transform(cls, input_data: GetContainerRequest) -> GetContainerDataClass:
        return GetContainerDataClass(
            container_id=input_data.container_id,
            network_name=input_data.network_name
        )


class GetContainerOutputDataTransformer(OutputDataTransformer):
    @classmethod
    def transform(cls, input_data: dict) -> ContainerResponse:
        return transform_container_response(input_data)
