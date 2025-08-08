from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer

# GRPC Data types
from container_maker_spec.types_pb2 import SaveContainerRequest
from container_maker_spec.types_pb2 import SaveContainerResponse
from container_maker_spec.types_pb2 import SavedPodResponse

# Container Maker Data types
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass


class SaveContainerInputDataTransformer(InputDataTransformer):
    @classmethod
    def transform(cls, input_data: SaveContainerRequest) -> SaveContainerDataClass:
        return SaveContainerDataClass(
            container_id=input_data.container_id,
            network_name=input_data.network_name
        )


class SaveContainerOutputDataTransformer(OutputDataTransformer):
    @classmethod
    def transform(cls, input_data: dict) -> SaveContainerResponse:
        return SaveContainerResponse(
            saved_pods=[
                SavedPodResponse(
                    pod_name=pod['pod_name'],
                    namespace_name=pod['namespace_name'],
                    image_name=pod['image_name'],
                ) for pod in input_data
            ]
        )
