# builtins
from unittest import TestCase

# modules
from src.containers.dataclasses.create_container_dataclass import ExposureLevel

# protobuf
from container_maker_spec.types_pb2 import CreateContainerRequest
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel
from container_maker_spec.types_pb2 import ContainerResponse

# data class
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass

# data transformers
from src.grpc.data_transformer.create_container_transformer import CreateContainerInputDataTransformer, CreateContainerOutputDataTransformer
from src.resources.dataclasses.pod.create_pod_dataclass import ResourceRequirementsDataClass


class TestCreateContainerTransformer(TestCase):

    def setUp(self) -> None:
        print('Test: setUp TestCreateContainer')
        self.container_name: str = 'test-container'
        self.namespace_name: str = 'test-namespace'
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.publish_information: list[dict] = [
            {'publish_port': 2222, 'target_port': 22, 'protocol': 'TCP'},
        ]
        self.environment_variables: dict[str, str] = {
            "SSH_PASSWORD": "12345678",
            "SSH_USERNAME": "test-user",
            "CONTAINER_ID": "1234567890",
            "DB_USERNAME": "testuser",
            "DB_PASSWORD": "testpassword",
            "DB_NAME": "testdb",
            "DB_HOST": "testhost",
            "DB_PORT": "5432",
            "DB_DATABASE": "testdatabase",
        }
        self.resource_requirements: ResourceRequirementsDataClass = ResourceRequirementsDataClass(
            cpu_request='100m',
            cpu_limit='1',
            memory_request='256Mi',
            memory_limit='1Gi',
            ephemeral_request='512Mi',
            ephemeral_limit='1Gi',
            snapshot_size_limit='2Gi',
        )
        # create the protobuf message
        self.grpc_create_container_request: CreateContainerRequest = CreateContainerRequest(
            container_name=self.container_name,
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=GRPCExposureLevel.EXPOSURE_LEVEL_INTERNAL,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements.to_dict()
        )

        self.container_id: str = '1234567890'
        self.container_ip: str = '127.0.0.1'
        self.container_ports: list[dict] = [
            {'name': 'ssh', 'container_port': 2222, 'protocol': 'TCP'},
            {'name': 'ssh', 'container_port': 2223, 'protocol': 'TCP'},
        ]
        self.container_associated_resources: list[dict] = [
            {
                'resource_name': 'test-container-pod',
                'resource_type': 'pod',
                'container_resources': {
                    'cpu_request': '100m',
                    'cpu_limit': '1',
                    'memory_request': '256Mi',
                    'memory_limit': '1Gi',
                    'ephemeral_request': '512Mi',
                    'ephemeral_limit': '1Gi',
                    'snapshot_size_limit': '2Gi',
                },
            }
        ]
        # container response
        self.container_response: dict = {
            'container_id': self.container_id,
            'container_name': self.container_name,
            'container_ip': self.container_ip,
            'container_network': self.namespace_name,
            'container_ports': self.container_ports,
            'container_associated_resources': self.container_associated_resources,
        }

    def test_create_container_input_data_transformer(self) -> None:
        '''
        Test the input data transformer.
        Should convert GRPC -> CreateContainerRequest to CreateContainerDataClass
        '''
        print('Test: test_create_container_input_data_transformer')
        input_data: CreateContainerDataClass = CreateContainerInputDataTransformer.transform(self.grpc_create_container_request)
        # basics
        self.assertEqual(input_data.container_name, self.container_name)
        self.assertEqual(input_data.network_name, self.namespace_name)
        self.assertEqual(input_data.image_name, self.image_name)
        # exposure level
        self.assertEqual(input_data.exposure_level, ExposureLevel.INTERNAL)
        # publish information
        self.assertEqual(input_data.publish_information[0].publish_port, self.publish_information[0]['publish_port'])
        self.assertEqual(input_data.publish_information[0].target_port, self.publish_information[0]['target_port'])
        self.assertEqual(input_data.publish_information[0].protocol, self.publish_information[0]['protocol'])
        self.assertEqual(input_data.publish_information[0].node_port, None)
        # environment variables
        self.assertEqual(input_data.environment_variables, self.environment_variables)

    def test_create_container_output_data_transformer(self) -> None:
        '''
        Test the output data transformer.
        Should convert dict -> ContainerResponse to GRPC -> ContainerResponse
        '''
        print('Test: test_create_container_output_data_transformer')
        output_data: ContainerResponse = CreateContainerOutputDataTransformer.transform(self.container_response)
        # basics
        self.assertEqual(output_data.container_name, self.container_name)
        self.assertEqual(output_data.container_id, self.container_id)
        self.assertEqual(output_data.container_ip, self.container_ip)
        self.assertEqual(output_data.container_network, self.namespace_name)
        # ports
        self.assertEqual(output_data.ports[0].name, self.container_ports[0]['name'])
        self.assertEqual(output_data.ports[0].container_port, self.container_ports[0]['container_port'])
        self.assertEqual(output_data.ports[0].protocol, self.container_ports[0]['protocol'])
        self.assertEqual(output_data.ports[1].name, self.container_ports[1]['name'])
        self.assertEqual(output_data.ports[1].container_port, self.container_ports[1]['container_port'])
        self.assertEqual(output_data.ports[1].protocol, self.container_ports[1]['protocol'])
        # associated resources
        self.assertEqual(len(output_data.associated_resources), 1)
        self.assertEqual(output_data.associated_resources[0].resource_name, self.container_associated_resources[0]['resource_name'])
        self.assertEqual(output_data.associated_resources[0].resource_type, self.container_associated_resources[0]['resource_type'])
        self.assertEqual(output_data.associated_resources[0].container_resources.cpu_request, self.container_associated_resources[0]['container_resources']['cpu_request'])
        self.assertEqual(output_data.associated_resources[0].container_resources.cpu_limit, self.container_associated_resources[0]['container_resources']['cpu_limit'])
        self.assertEqual(output_data.associated_resources[0].container_resources.memory_request, self.container_associated_resources[0]['container_resources']['memory_request'])
        self.assertEqual(output_data.associated_resources[0].container_resources.memory_limit, self.container_associated_resources[0]['container_resources']['memory_limit'])
        self.assertEqual(output_data.associated_resources[0].container_resources.ephemeral_request, self.container_associated_resources[0]['container_resources']['ephemeral_request'])
        self.assertEqual(output_data.associated_resources[0].container_resources.ephemeral_limit, self.container_associated_resources[0]['container_resources']['ephemeral_limit'])
        self.assertEqual(output_data.associated_resources[0].container_resources.snapshot_size_limit, self.container_associated_resources[0]['container_resources']['snapshot_size_limit'])
