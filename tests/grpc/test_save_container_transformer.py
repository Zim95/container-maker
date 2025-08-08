# built-in
from unittest import TestCase

# protobuf
from container_maker_spec.types_pb2 import SaveContainerRequest
from container_maker_spec.types_pb2 import SaveContainerResponse

# data class
from src.containers.dataclasses.save_container_dataclass import SaveContainerDataClass

# data transformers
from src.grpc.data_transformer.save_container_transformer import SaveContainerInputDataTransformer, SaveContainerOutputDataTransformer


class TestSaveContainerTransformer(TestCase):
    def setUp(self) -> None:
        print('Test: setUp TestSaveContainer')
        self.container_id: str = '1234567890'
        self.namespace_name: str = 'test-namespace'
        # create the protobuf message
        self.grpc_save_container_request: SaveContainerRequest = SaveContainerRequest(
            container_id=self.container_id,
            network_name=self.namespace_name
        )

        # saved pod response
        self.saved_pod_response: dict = {
            'pod_name': 'test-pod',
            'namespace_name': self.namespace_name,
            'image_name': 'test-image',
        }
        self.saved_pod_response_list: list[dict] = [self.saved_pod_response]

    def test_save_container_input_data_transformer(self) -> None:
        '''
        Test the input data transformer.
        Should convert GRPC -> SaveContainerRequest to SaveContainerDataClass
        '''
        print('Test: test_save_container_input_data_transformer')
        input_data: SaveContainerDataClass = SaveContainerInputDataTransformer.transform(self.grpc_save_container_request)
        # basics
        self.assertEqual(input_data.container_id, self.container_id)
        self.assertEqual(input_data.network_name, self.namespace_name)

    def test_save_container_output_data_transformer(self) -> None:
        '''
        Test the output data transformer.
        Should convert dict -> SaveContainerResponse to GRPC -> SaveContainerResponse
        '''
        print('Test: test_save_container_output_data_transformer')
        output_data: SaveContainerResponse = SaveContainerOutputDataTransformer.transform(self.saved_pod_response_list)
        # basics
        self.assertEqual(output_data.saved_pods[0].pod_name, self.saved_pod_response['pod_name'])
        self.assertEqual(output_data.saved_pods[0].namespace_name, self.saved_pod_response['namespace_name'])
        self.assertEqual(output_data.saved_pods[0].image_name, self.saved_pod_response['image_name'])
