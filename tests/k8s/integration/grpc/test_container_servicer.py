'''
Here we will NOT use the stub to test the create container API.
This is because, the stub implementation happens outside of the container maker api.
This test needs to happen on the client that will use the container maker api.

Here we will simply test the creation of container API from the container maker servicer.
'''
# builtins
import time
from unittest import TestCase

import paramiko

# grpc
from src.grpc.servicer import ContainerMakerAPIServicerImpl
from container_maker_spec.types_pb2 import CreateContainerRequest, ListContainerRequest, DeleteContainerRequest
from container_maker_spec.types_pb2 import ContainerResponse, ListContainerResponse, DeleteContainerResponse, SaveContainerRequest, SaveContainerResponse
from container_maker_spec.types_pb2 import ExposureLevel as GRPCExposureLevel


# dataclasses
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.namespace_manager import NamespaceManager


NAMESPACE_NAME: str = 'test-grpc-namespace'


class TestGRPCContainerServicer(TestCase):
    """
    Test the GRPC container servicer.
    """
    def setUp(self) -> None:
        print('Test: setUp TestGRPCContainerServicer')
        self.container_name: str = 'test-container'
        self.namespace_name: str = NAMESPACE_NAME
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.publish_information: list[dict] = [
            {'publish_port': 2222, 'target_port': 22, 'protocol': 'TCP'},
        ]
        self.environment_variables: dict[str, str] = {
            'SSH_PASSWORD': '12345678',
            'SSH_USERNAME': 'test-user',
        }
        # create the protobuf message
        self.grpc_create_container_request: CreateContainerRequest = CreateContainerRequest(
            container_name=self.container_name,
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=GRPCExposureLevel.EXPOSURE_LEVEL_EXPOSED,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )
        self.container_maker_servicer: ContainerMakerAPIServicerImpl = ContainerMakerAPIServicerImpl()

    def test_a_creation_and_deletion_of_container(self) -> None:
        '''
        Should create a container and then delete it.
        '''
        print('Test: test_a_creation_and_deletion_of_container')
        # list the containers, there shouldn't be any
        init_containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(init_containers.containers), 0)
        # create the container
        container_response: ContainerResponse = self.container_maker_servicer.createContainer(self.grpc_create_container_request, None)
        # list the containers, there should be one
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 1)

        # assert the values of the container
        self.assertEqual(container_response.container_name, f'{self.container_name}-ingress')
        self.assertEqual(container_response.container_network, self.namespace_name)
        self.assertEqual(container_response.container_ip is not None, True)
        self.assertEqual(container_response.ports[0].name, 'http')
        self.assertEqual(container_response.ports[0].container_port, 80)
        self.assertEqual(container_response.ports[0].protocol, 'TCP')
        self.assertEqual(container_response.ports[1].name, 'https')
        self.assertEqual(container_response.ports[1].container_port, 443)
        self.assertEqual(container_response.ports[1].protocol, 'TCP')

        # delete the container
        delete_container_response: DeleteContainerResponse = self.container_maker_servicer.deleteContainer(DeleteContainerRequest(
            container_id=container_response.container_id,
            network_name=self.namespace_name,
        ), None)
        self.assertEqual(delete_container_response.container_id, container_response.container_id)
        self.assertEqual(delete_container_response.status, 'Deleted')
        # list the containers, there should be no containers
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 0)

    def test_b_creation_and_deletion_of_duplicate_container(self) -> None:
        '''
        Should return the existing container and then delete it.
        '''
        print('Test: test_b_creation_and_deletion_of_duplicate_container')
        # list the containers, there shouldn't be any
        init_containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(init_containers.containers), 0)
        # create the containers
        first_container: ContainerResponse = self.container_maker_servicer.createContainer(self.grpc_create_container_request, None)
        second_container: ContainerResponse = self.container_maker_servicer.createContainer(self.grpc_create_container_request, None)
        # list the containers, there should be only one, no duplicates
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 1)
        # assert the values of the container
        self.assertEqual(first_container.container_name, second_container.container_name)
        self.assertEqual(first_container.container_network, second_container.container_network)
        self.assertEqual(first_container.container_ip, second_container.container_ip)
        self.assertEqual(first_container.ports[0].name, second_container.ports[0].name)
        self.assertEqual(first_container.ports[0].container_port, second_container.ports[0].container_port)
        self.assertEqual(first_container.ports[0].protocol, second_container.ports[0].protocol)
        self.assertEqual(first_container.ports[1].name, second_container.ports[1].name)
        self.assertEqual(first_container.ports[1].container_port, second_container.ports[1].container_port)
        self.assertEqual(first_container.ports[1].protocol, second_container.ports[1].protocol)

        # delete the container
        delete_container_response: DeleteContainerResponse = self.container_maker_servicer.deleteContainer(DeleteContainerRequest(
            container_id=first_container.container_id,
            network_name=self.namespace_name,
        ), None)
        self.assertEqual(delete_container_response.container_id, first_container.container_id)
        self.assertEqual(delete_container_response.status, 'Deleted')
        # list the containers, there should be no containers
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 0)

    def test_c_ssh_into_container(self) -> None:
        '''
        Should ssh into the container and then delete it.
        Ingress will not work for SSH, we need to use CLUSTER_LOCAL or CLUSTER_EXTERNAL.
        For this test, we will use CLUSTER_LOCAL.
        '''
        print('Test: test_c_ssh_into_container')
        self.grpc_create_container_request.exposure_level = GRPCExposureLevel.EXPOSURE_LEVEL_CLUSTER_LOCAL
        container_response: ContainerResponse = self.container_maker_servicer.createContainer(self.grpc_create_container_request, None)
        print('Waiting for container to be ready')
        time.sleep(10)
        print('Service is ready')
        ssh: paramiko.SSHClient = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(
                hostname=container_response.container_ip,
                username=self.environment_variables['SSH_USERNAME'],
                password=self.environment_variables['SSH_PASSWORD'],
                port=container_response.ports[0].container_port
            )
            _, stdout, _ = ssh.exec_command('echo "SSH test successful"')
            output = stdout.read().decode().strip()
            self.assertEqual(output, "SSH test successful")
        finally:
            ssh.close()
            self.container_maker_servicer.deleteContainer(DeleteContainerRequest(
                container_id=container_response.container_id,
                network_name=self.namespace_name,
            ), None)

    def test_d_creation_of_container_with_invalid_image(self) -> None:
        '''
        Should raise a timeout error and then delete the container.
        '''
        print('Test: test_d_creation_of_container_with_invalid_image')
        self.grpc_create_container_request.image_name = 'invalid-image'
        self.grpc_create_container_request.exposure_level = GRPCExposureLevel.EXPOSURE_LEVEL_EXPOSED
        container_id: str | None = None
        try:
            container_response: ContainerResponse = self.container_maker_servicer.createContainer(self.grpc_create_container_request, None)
            container_id = container_response.container_id
        except TimeoutError as e:
            self.assertEqual(str(e), f"Timeout waiting for pod {f'{self.container_name}-pod'} to reach status Running after {20.0} seconds")
            self.grpc_create_container_request.image_name = 'zim95/ssh_ubuntu:latest'  # set it back to the normal image for the rest of the tests.
        # delete the existing pod. Otherwise the new pod will not be created. it will simply fetch the existing pod.
        # the existing pod will have the same image error and the rest of the tests will not work.
        if container_id is not None:
            self.container_maker_servicer.deleteContainer(DeleteContainerRequest(
                container_id=container_id,
                network_name=self.namespace_name,
            ), None)


    def test_e_creation_of_container_with_invalid_exposure_level(self) -> None:
        '''
        Should raise a invalid exposure level error and then delete the container.
        '''
        pass

    def test_f_websocket_into_container(self) -> None:
        '''
        Should websocket into the container and then delete it.
        '''
        pass

    def test_g_creation_of_container_with_empty_environment_variables(self) -> None:
        '''
        Everything should work as normal.
        '''
        print('Test: test_g_creation_of_container_with_empty_environment_variables')
        # list the containers, there shouldn't be any
        init_containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(init_containers.containers), 0)
        # create the container
        grpc_create_container_request: CreateContainerRequest = CreateContainerRequest(
            container_name=self.container_name,
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=GRPCExposureLevel.EXPOSURE_LEVEL_EXPOSED,
            publish_information=self.publish_information,
            environment_variables={},
        )
        container_response: ContainerResponse = self.container_maker_servicer.createContainer(grpc_create_container_request, None)
        # list the containers, there should be one
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 1)

        # assert the values of the container
        self.assertEqual(container_response.container_name, f'{self.container_name}-ingress')
        self.assertEqual(container_response.container_network, self.namespace_name)
        self.assertEqual(container_response.container_ip is not None, True)
        self.assertEqual(container_response.ports[0].name, 'http')
        self.assertEqual(container_response.ports[0].container_port, 80)
        self.assertEqual(container_response.ports[0].protocol, 'TCP')
        self.assertEqual(container_response.ports[1].name, 'https')
        self.assertEqual(container_response.ports[1].container_port, 443)
        self.assertEqual(container_response.ports[1].protocol, 'TCP')

        # delete the container
        delete_container_response: DeleteContainerResponse = self.container_maker_servicer.deleteContainer(DeleteContainerRequest(
            container_id=container_response.container_id,
            network_name=self.namespace_name,
        ), None)
        self.assertEqual(delete_container_response.container_id, container_response.container_id)
        self.assertEqual(delete_container_response.status, 'Deleted')
        # list the containers, there should be no containers
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 0)

    def test_h_save_container(self) -> None:
        '''
        Should save a container and then delete it.
        '''
        print('Test: test_h_save_container')
        # list the containers, there shouldn't be any
        init_containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(init_containers.containers), 0)
        # create the container
        container_response: ContainerResponse = self.container_maker_servicer.createContainer(self.grpc_create_container_request, None)
        # save the container
        save_container_response: SaveContainerResponse = self.container_maker_servicer.saveContainer(SaveContainerRequest(
            container_id=container_response.container_id,
            network_name=self.namespace_name,
        ), None)
        # list the containers, there should be one
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 1)
        # assert the values of the saved container
        self.assertEqual(save_container_response.saved_pods[0].pod_name, f'{self.container_name}-pod')
        self.assertEqual(save_container_response.saved_pods[0].namespace_name, self.namespace_name)
        self.assertEqual(save_container_response.saved_pods[0].image_name, f'{self.container_name}-pod-image:latest')
        # delete the container
        delete_container_response: DeleteContainerResponse = self.container_maker_servicer.deleteContainer(DeleteContainerRequest(
            container_id=container_response.container_id,
            network_name=self.namespace_name,
        ), None)
        self.assertEqual(delete_container_response.container_id, container_response.container_id)
        self.assertEqual(delete_container_response.status, 'Deleted')
        # list the containers, there should be no containers
        containers: ListContainerResponse = self.container_maker_servicer.listContainer(ListContainerRequest(network_name=self.namespace_name), None)
        self.assertEqual(len(containers.containers), 0)

    def tearDown(self) -> None:
        '''
        Delete the namespace if it exists.
        '''
        namespaces: list[dict] = NamespaceManager.list()
        namespace_names: list[str] = [namespace['namespace_name'] for namespace in namespaces]
        if NAMESPACE_NAME in namespace_names:
            NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
