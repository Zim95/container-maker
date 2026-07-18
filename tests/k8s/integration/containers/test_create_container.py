# builtins
from unittest import TestCase

# modules
from src.containers.containers import KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.resources.dataclasses.ingress.create_ingress_dataclass import CreateIngressDataClass
from src.resources.dataclasses.ingress.delete_ingress_dataclass import DeleteIngressDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import ResourceRequirementsDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.create_service_dataclass import CreateServiceDataClass, PublishInformationDataClass, ServiceType
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager
from src.common.utils import generate_timestamp_suffix
import src.common.config as config


NAMESPACE_NAME: str = 'test-create-container'


class TestCreateContainer(TestCase):
    def setUp(self) -> None:
        '''
        Setup the container data.
        Note:
        1. We need the tests to be in order because we set the container_id accordingly.
        2. There is a chance of the internal container test running last.
        3. All other tests will atleast create a service. If the ingress test runs second last,
            it will create ingress, service and pod and set the container id.
        4. In the teardown, it deletes only the ingress, and when it tries to delete lingering services,
            the service will not be deleted because it is attached to a pod and therefore not lingering by nature.
        5. So when the internal container test runs last, it will fail because it expects len(services) == 0 but the
            service from previous test exists, so it will fail.
        6. Therefore we need to maintain the order of creation.
        7. The order is: internal -> cluster_local -> cluster_external -> exposed.
        '''
        print('Test: setUp TestCreateContainer')
        self.container_name: str = 'test-container'
        self.namespace_name: str = NAMESPACE_NAME
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.exposure_level: ExposureLevel = ExposureLevel.INTERNAL
        self.resource_requirements: ResourceRequirementsDataClass = ResourceRequirementsDataClass(
            cpu_request='100m',
            cpu_limit='1',
            memory_request='256Mi',
            memory_limit='1Gi',
            ephemeral_request='512Mi',
            ephemeral_limit='1Gi',
            snapshot_size_limit='2Gi',
        )
        self.publish_information: list[PublishInformationDataClass] = [
            PublishInformationDataClass(publish_port=2222, target_port=22, protocol='TCP'),
        ]
        self.environment_variables: dict = {
            "SSH_USERNAME": "ubuntu",
            "SSH_PASSWORD": "testpwd",
            "CONTAINER_ID": "1234567890",
            "DB_USERNAME": "testuser",
            "DB_PASSWORD": "testpassword",
            "DB_NAME": "testdb",
            "DB_HOST": "testhost",
            "DB_PORT": "5432",
            "DB_DATABASE": "testdatabase",
        }
        self.container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=self.container_name,
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=self.exposure_level,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )

    def test_a_creation_of_container_internal(self) -> None:
        '''
        Test the creation of a container with an internal exposure level.
        Result: Only the pod is created.
        '''
        print('Test: test_creation_of_container_internal')
        self.container_data.exposure_level = ExposureLevel.INTERNAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # only the pod is created.
        self.assertEqual(len(services), 0)
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        # Pod name now includes timestamp: test-container-pod-1706565890
        self.assertTrue(container['container_name'].startswith(f'{self.container_name}-pod-'))
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 22)
        # resources check
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['cpu_request'], '100m')
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['cpu_limit'], '1')
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['memory_request'], '256Mi')
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['memory_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['ephemeral_request'], '512Mi')
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['ephemeral_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['container_resources']['snapshot_size_limit'], '2Gi')

    def test_b_creation_of_container_cluster_local(self) -> None:
        '''
        Test the creation of a container with an cluster local exposure level.
        Result: Service is created with a cluster local ip.
        '''
        print('Test: test_creation_of_container_cluster_local')
        self.container_data.exposure_level = ExposureLevel.CLUSTER_LOCAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # pod is created.
        self.assertEqual(len(services), 1)  # service of type cluster ip is created
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertTrue(container['container_name'].startswith(f'{self.container_name}-service-'))
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 2222)
        # resources check
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['cpu_request'], '100m')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['cpu_limit'], '1')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['memory_request'], '256Mi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['memory_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['ephemeral_request'], '512Mi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['ephemeral_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['snapshot_size_limit'], '2Gi')

    def test_c_creation_of_container_cluster_external(self) -> None:
        '''
        Test the creation of a container with an cluster external exposure level.
        Result: Service is created with a cluster external ip.
        '''
        print('Test: test_creation_of_container_cluster_external')
        self.container_data.exposure_level = ExposureLevel.CLUSTER_EXTERNAL
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # pod is created.
        self.assertEqual(len(services), 1)  # service of type load balancer is created
        self.assertEqual(len(ingresses), 0)

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertTrue(container['container_name'].startswith(f'{self.container_name}-service-'))
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 1)
        self.assertEqual(container['container_ports'][0]['container_port'], 2222)
        # resources check
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['cpu_request'], '100m')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['cpu_limit'], '1')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['memory_request'], '256Mi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['memory_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['ephemeral_request'], '512Mi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['ephemeral_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['container_resources']['snapshot_size_limit'], '2Gi')

    def test_d_creation_of_container_exposed(self) -> None:
        '''
        Test the creation of a container with an exposed exposure level.
        Result: Ingress is created with a cluster external ip.
        '''
        print('Test: test_creation_of_container_exposed')
        self.container_data.exposure_level = ExposureLevel.EXPOSED
        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id: str = container['container_id']
        # list pods, services and ingresses.
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        ingresses: list[dict] = IngressManager.list(ListIngressDataClass(namespace_name=self.namespace_name))

        # assert the length of the lists.
        self.assertEqual(len(pods), 1)  # pod is created.
        self.assertEqual(len(services), 1)  # service of type load balancer is created
        self.assertEqual(len(ingresses), 1)  # ingress is created

        # validate container properties
        self.assertEqual(len(container['container_id']), 36)
        self.assertTrue(container['container_name'].startswith(f'{self.container_name}-ingress-'))
        self.assertIsNotNone(container['container_ip'])
        self.assertEqual(container['container_network'], self.namespace_name)
        self.assertEqual(len(container['container_ports']), 2)
        # resources check
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['cpu_request'], '100m')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['cpu_limit'], '1')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['memory_request'], '256Mi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['memory_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['ephemeral_request'], '512Mi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['ephemeral_limit'], '1Gi')
        self.assertEqual(container['container_associated_resources'][0]['associated_resources'][0]['associated_resources'][0]['container_resources']['snapshot_size_limit'], '2Gi')

    def test_e_recreate_pod_with_same_name(self) -> None:
        '''
        Create a pod, delete it, and recreate with the same base name.
        A new pod with a new timestamp should be created.
        '''
        print('Test: test_recreate_pod_with_same_name')
        self.container_data.exposure_level = ExposureLevel.INTERNAL
        self.container_data.container_name = f'{self.container_name}-recreate-pod'

        first: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id = first['container_id']
        first_pod_name: str = first['container_name']

        PodManager.delete(DeletePodDataClass(
            namespace_name=self.namespace_name,
            pod_name=first_pod_name,
        ))

        second: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id = second['container_id']
        second_pod_name: str = second['container_name']

        self.assertNotEqual(first_pod_name, second_pod_name)
        self.assertTrue(second_pod_name.startswith(f'{self.container_data.container_name}-pod-'))

    def test_f_recreate_service_with_same_pod(self) -> None:
        '''
        Create a pod and service, delete the service, then create another service
        targeting the same pod labels. The new service should be created.
        '''
        print('Test: test_recreate_service_with_same_pod')
        self.container_data.exposure_level = ExposureLevel.CLUSTER_LOCAL
        self.container_data.container_name = f'{self.container_name}-recreate-service'

        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id = container['container_id']
        first_service_name: str = container['container_name']

        ServiceManager.delete(DeleteServiceDataClass(
            namespace_name=self.namespace_name,
            service_name=first_service_name,
        ))

        new_service_name: str = f'{self.container_data.container_name}-service-{generate_timestamp_suffix()}'
        recreated: dict = ServiceManager.create(CreateServiceDataClass(
            service_name=new_service_name,
            pod_label_selector=self.container_data.container_name,
            namespace_name=self.namespace_name,
            publish_information=self.publish_information,
            service_type=ServiceType.CLUSTER_IP,
        ))

        self.assertEqual(recreated['service_name'], new_service_name)
        self.assertNotEqual(first_service_name, new_service_name)

        ServiceManager.delete(DeleteServiceDataClass(
            namespace_name=self.namespace_name,
            service_name=new_service_name,
        ))
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        for pod in pods:
            PodManager.delete(DeletePodDataClass(
                namespace_name=self.namespace_name,
                pod_name=pod['pod_name'],
            ))
        self.container_id = None

    def test_g_recreate_ingress_with_same_service(self) -> None:
        '''
        Create an ingress, delete it, and recreate a new ingress pointing to the same service.
        The new ingress should be created with a new name.
        '''
        print('Test: test_recreate_ingress_with_same_service')
        self.container_data.exposure_level = ExposureLevel.EXPOSED
        self.container_data.container_name = f'{self.container_name}-recreate-ingress'

        container: dict = KubernetesContainerManager.create(self.container_data)
        self.container_id = container['container_id']
        first_ingress_name: str = container['container_name']

        IngressManager.delete(DeleteIngressDataClass(
            namespace_name=self.namespace_name,
            ingress_name=first_ingress_name,
        ))

        services: list[dict] = ServiceManager.list(ListServiceDataClass(namespace_name=self.namespace_name))
        self.assertEqual(len(services), 1)
        service: dict = services[0]

        new_ingress_name: str = f'{self.container_data.container_name}-ingress-{generate_timestamp_suffix()}'
        recreated: dict = IngressManager.create(CreateIngressDataClass(
            namespace_name=self.namespace_name,
            ingress_name=new_ingress_name,
            service_name=service['service_name'],
            host=config.INGRESS_HOST,
            service_ports=service['service_ports'],
        ))

        self.assertEqual(recreated['ingress_name'], new_ingress_name)
        self.assertNotEqual(first_ingress_name, new_ingress_name)

        IngressManager.delete(DeleteIngressDataClass(
            namespace_name=self.namespace_name,
            ingress_name=new_ingress_name,
        ))
        ServiceManager.delete(DeleteServiceDataClass(
            namespace_name=self.namespace_name,
            service_name=service['service_name'],
        ))
        pods: list[dict] = PodManager.list(ListPodDataClass(namespace_name=self.namespace_name))
        for pod in pods:
            PodManager.delete(DeletePodDataClass(
                namespace_name=self.namespace_name,
                pod_name=pod['pod_name'],
            ))
        self.container_id = None

    def tearDown(self) -> None:
        '''
        Remove the container after every test.
        This deletes lingering namespaces as well. So no need for cleanup.
        '''
        if self.container_id:
            KubernetesContainerManager.delete(DeleteContainerDataClass(
                container_id=self.container_id,
                network_name=self.namespace_name,
            ))
