from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer

# GRPC Data types
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PortInformation

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
        return ContainerResponse(
            container_id=input_data['container_id'],
            container_name=input_data['container_name'],
            container_ip=input_data['container_ip'],
            container_network=input_data['container_network'],
            ports=[PortInformation(
                name=port['name'],
                container_port=port['container_port'],
                protocol=port['protocol'],
            ) for port in input_data['container_ports']],
        )
