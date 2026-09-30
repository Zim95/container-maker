from src.grpc.data_transformer import InputDataTransformer, OutputDataTransformer, transform_container_response

# GRPC Data types
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse

# Container Maker Data types
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass
from src.containers.dataclasses.create_container_dataclass import ExposureLevel
from src.containers.dataclasses.create_container_dataclass import PublishInformationDataClass
from src.containers.dataclasses.create_container_dataclass import ResourceRequirementsDataClass


class CreateContainerInputDataTransformer(InputDataTransformer):
    @classmethod
    def transform(cls, input_data: CreateContainerRequest) -> CreateContainerDataClass:
        exposure_level_map: dict = {
            0: ExposureLevel.INTERNAL,  # proto EXPOSURE_LEVEL_UNSPECIFIED - browseterm-server always sends this
            1: ExposureLevel.INTERNAL,
            2: ExposureLevel.CLUSTER_LOCAL,
            3: ExposureLevel.CLUSTER_EXTERNAL,
            4: ExposureLevel.EXPOSED
        }
        # Fail safe toward INTERNAL (pod only, no Service) for any unrecognized value, not
        # CLUSTER_LOCAL - defaulting to CLUSTER_LOCAL silently created a ClusterIP Service for
        # every container (browseterm-server always sends 0, which wasn't in this map), and
        # Containers.create() returns the LAST-created resource's IP as container_ip - so every
        # Create/Resume was handing back the Service's ClusterIP instead of the pod's real IP.
        # socket-ssh connects directly to that IP on port 22; a freshly-created ClusterIP has a
        # window before kube-proxy programs its DNAT rule where that connection just hangs until
        # timeout. Caught live 2026-09-30: containers.ip_address held a 10.43.x.x Service IP,
        # only corrected minutes later by status_monitor's resource_reconciler.py periodic sweep.
        exposure_level: ExposureLevel = exposure_level_map.get(input_data.exposure_level, ExposureLevel.INTERNAL)
        publish_information: list[PublishInformationDataClass] = [
            PublishInformationDataClass(
                publish_port=publish_info.publish_port,
                target_port=publish_info.target_port,
                protocol=publish_info.protocol,
                # Add node port too, but only if it is not 0. In GRPC 0 is the default value for an unset integer field.
                node_port=publish_info.node_port if publish_info.node_port != 0 else None,
            ) for publish_info in input_data.publish_information
        ]
        # Transform resource requirements if provided
        resource_requirements = ResourceRequirementsDataClass()
        if input_data.HasField('resource_requirements'):
            rr = input_data.resource_requirements
            resource_requirements = ResourceRequirementsDataClass(
                cpu_request=rr.cpu_request if rr.cpu_request else '100m',
                cpu_limit=rr.cpu_limit if rr.cpu_limit else '1',
                memory_request=rr.memory_request if rr.memory_request else '256Mi',
                memory_limit=rr.memory_limit if rr.memory_limit else '1Gi',
                ephemeral_request=rr.ephemeral_request if rr.ephemeral_request else '512Mi',
                ephemeral_limit=rr.ephemeral_limit if rr.ephemeral_limit else '1Gi',
                snapshot_size_limit=rr.snapshot_size_limit if rr.snapshot_size_limit else '2Gi',
            )
        return CreateContainerDataClass(
            image_name=input_data.image_name,
            container_name=input_data.container_name,
            network_name=input_data.network_name,
            exposure_level=exposure_level,
            publish_information=publish_information,
            environment_variables=input_data.environment_variables,
            resource_requirements=resource_requirements,
        )


class CreateContainerOutputDataTransformer(OutputDataTransformer):
    @classmethod
    def transform(cls, input_data: dict) -> ContainerResponse:
        return transform_container_response(input_data)
