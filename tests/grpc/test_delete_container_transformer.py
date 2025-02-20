# built-in
from unittest import TestCase

# protobuf
from container_maker_spec.types_pb2 import DeleteContainerRequest
from container_maker_spec.types_pb2 import DeleteContainerResponse

# data class
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass

# data transformers
from src.grpc.data_transformer.delete_container_transformer import DeleteContainerInputDataTransformer, DeleteContainerOutputDataTransformer


class TestDeleteContainerTransformer(TestCase):
    def setUp(self) -> None:
        print('Test: setUp TestDeleteContainer')
        self.container_id: str = '1234567890'
        self.namespace_name: str = 'test-namespace'
        # create the protobuf message
        self.grpc_delete_container_request: DeleteContainerRequest = DeleteContainerRequest(
            container_id=self.container_id,
            network_name=self.namespace_name
        )
        # container response
        self.container_response: dict = {
            'container_id': self.container_id,
            'status': 'success',
        }

    def test_delete_container_input_data_transformer(self) -> None:
        '''
        Test the input data transformer.
        Should convert GRPC -> DeleteContainerRequest to DeleteContainerDataClass
        '''
        print('Test: test_delete_container_input_data_transformer')
        input_data: DeleteContainerDataClass = DeleteContainerInputDataTransformer.transform(self.grpc_delete_container_request)
        # basics
        self.assertEqual(input_data.container_id, self.container_id)
        self.assertEqual(input_data.network_name, self.namespace_name)

    def test_delete_container_output_data_transformer(self) -> None:
        '''
        Test the output data transformer.
        Should convert dict -> DeleteContainerResponse to GRPC -> DeleteContainerResponse
        '''
        print('Test: test_delete_container_output_data_transformer')
        output_data: DeleteContainerResponse = DeleteContainerOutputDataTransformer.transform(self.container_response)
        # basics
        self.assertEqual(output_data.container_id, self.container_id)
        self.assertEqual(output_data.status, self.container_response['status'])
