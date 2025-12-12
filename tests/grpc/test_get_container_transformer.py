# built-in
from unittest import TestCase

# protobuf
from container_maker_spec.types_pb2 import GetContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse

# data class
from src.containers.dataclasses.get_container_dataclass import GetContainerDataClass

# data transformers
from src.grpc.data_transformer.get_container_transformer import GetContainerInputDataTransformer, GetContainerOutputDataTransformer


class TestGetContainerTransformer(TestCase):
    def setUp(self) -> None:
        print('Test: setUp TestGetContainer')
        self.container_id: str = '1234567890'
        self.namespace_name: str = 'test-namespace'
        # create the protobuf message
        self.grpc_get_container_request: GetContainerRequest = GetContainerRequest(
            container_id=self.container_id,
            network_name=self.namespace_name
        )

        # response data
        self.container_ip: str = '127.0.0.1'
        self.container_name: str = 'test-container'
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

    def test_get_container_input_data_transformer(self) -> None:
        '''
        Test the input data transformer.
        Should convert GRPC -> GetContainerRequest to GetContainerDataClass
        '''
        print('Test: test_get_container_input_data_transformer')
        input_data: GetContainerDataClass = GetContainerInputDataTransformer.transform(self.grpc_get_container_request)
        # basics
        self.assertEqual(input_data.container_id, self.container_id)
        self.assertEqual(input_data.network_name, self.namespace_name)

    def test_get_container_output_data_transformer(self) -> None:
        '''
        Test the output data transformer.
        Should convert dict -> ContainerResponse to GRPC -> ContainerResponse
        '''
        print('Test: test_get_container_output_data_transformer')
        output_data: ContainerResponse = GetContainerOutputDataTransformer.transform(self.container_response)
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
