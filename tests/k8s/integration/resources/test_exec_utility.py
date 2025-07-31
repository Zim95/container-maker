# builtins
from unittest import TestCase

# local
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.pod_manager import PodManager, ExecUtility
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass


NAMESPACE_NAME: str = 'test-exec-utility'
POD_NAME: str = 'test-ssh-pod'


class TestExecUtility(TestCase):
    def setUp(self) -> None:
        '''
        Setup the test environment.
        '''
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.pod_name: str = POD_NAME
        self.namespace_name: str = NAMESPACE_NAME
        self.target_ports: set = {22, 23}
        self.environment_variables: dict = {
            "SSH_USERNAME": "ubuntu",
            "SSH_PASSWORD": "testpwd"
        }
        self.create_pod_data: CreatePodDataClass = CreatePodDataClass(
            image_name=self.image_name,
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            target_ports=self.target_ports,
            environment_variables=self.environment_variables,
        )
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))
        self.pod: dict = PodManager.create(self.create_pod_data)

    def test_run_command(self) -> None:
        '''
        Test the run_command_with_output method.
        '''
        print('Test: test_run_command')
        # run a command
        output: str = ExecUtility.run_command(self.pod_name, self.namespace_name, self.pod_name, 'ls -l')
        # check if the command ran successfully
        self.assertEqual(int(output.split('\n')[0].split(' ')[-1]) > 0, True)
        print('Command ran successfully.')

    def test_run_command_with_stream(self) -> None:
        '''
        Test the run_command_with_stream method.
        '''
        print('Test: test_run_command_with_stream')
        # run a command
        output: str = ExecUtility.run_command_with_stream(self.pod_name, self.namespace_name, self.pod_name, 'apt-get update')
        # check assert
        self.assertEqual('Hit:1' in output, True)
        print('Command ran successfully.')


class ZZZ_Cleanup(TestCase):
    def test_cleanup(self) -> None:
        '''
        Cleanup the test environment.
        '''
        print('Cleaning up pod...')
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': NAMESPACE_NAME,
            'pod_name': POD_NAME
        }))
        print('Cleaning up namespace...')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
        print('Cleanup complete.')
