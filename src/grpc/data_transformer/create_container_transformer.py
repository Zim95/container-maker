from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer

# GRPC Data types
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse
from container_maker_spec.types_pb2 import PortInformation

# Container Maker Data types
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass
from src.containers.dataclasses.create_container_dataclass import ExposureLevel
from src.containers.dataclasses.create_container_dataclass import PublishInformationDataClass


class CreateContainerInputDataTransformer(InputDataTransformer):
    @classmethod
    def transform(cls, input_data: CreateContainerRequest) -> CreateContainerDataClass:
        exposure_level_map: dict = {
            1: ExposureLevel.INTERNAL,
            2: ExposureLevel.CLUSTER_LOCAL,
            3: ExposureLevel.CLUSTER_EXTERNAL,
            4: ExposureLevel.EXPOSED
        }
        exposure_level: ExposureLevel = exposure_level_map.get(input_data.exposure_level, ExposureLevel.CLUSTER_LOCAL)
        publish_information: list[PublishInformationDataClass] = [
            PublishInformationDataClass(
                publish_port=publish_info.publish_port,
                target_port=publish_info.target_port,
                protocol=publish_info.protocol,
            ) for publish_info in input_data.publish_information
        ]
        return CreateContainerDataClass(
            image_name=input_data.image_name,
            container_name=input_data.container_name,
            network_name=input_data.network_name,
            exposure_level=exposure_level,
            publish_information=publish_information,
            environment_variables=input_data.environment_variables,
        )


class CreateContainerOutputDataTransformer(OutputDataTransformer):
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
