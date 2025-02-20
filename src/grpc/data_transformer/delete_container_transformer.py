from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer

# GRPC Data types
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerResponse
# Container Maker Data types
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass


class DeleteContainerInputDataTransformer(InputDataTransformer):
    @classmethod
    def transform(cls, input_data: DeleteContainerRequest) -> DeleteContainerDataClass:
        return DeleteContainerDataClass(
            container_id=input_data.container_id,
            network_name=input_data.network_name
        )


class DeleteContainerOutputDataTransformer(OutputDataTransformer):
    @classmethod
    def transform(cls, input_data: dict) -> DeleteContainerResponse:
        return DeleteContainerResponse(
            container_id=input_data['container_id'],
            status=input_data['status']
        )
