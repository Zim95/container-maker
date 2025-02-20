from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer

# GRPC Data types
from container_maker_spec.types_pb2 import ListContainerRequest
from container_maker_spec.types_pb2 import ListContainerResponse
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PortInformation
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
                ContainerResponse(
                    container_id=container['container_id'],
                    container_name=container['container_name'],
                    container_ip=container['container_ip'],
                    container_network=container['container_network'],
                    ports=[PortInformation(
                        name=port['name'],
                        container_port=port['container_port'],
                        protocol=port['protocol'],
                    ) for port in container['container_ports']],
                ) for container in input_data
            ]
        )
