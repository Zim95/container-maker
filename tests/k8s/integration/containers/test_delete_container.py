# builtins
from unittest import TestCase

# modules
from src.containers.containers import KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel
from src.containers.dataclasses.delete_container_dataclass import DeleteContainerDataClass
from src.resources.dataclasses.ingress.list_ingress_dataclass import ListIngressDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.service.create_service_dataclass import PublishInformationDataClass
from src.resources.dataclasses.service.list_service_dataclass import ListServiceDataClass
from src.resources.ingress_manager import IngressManager
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager
from src.resources.service_manager import ServiceManager


NAMESPACE_NAME: str = 'test-delete-container'


class TestDeleteContainer(TestCase):
    def setUp(self) -> None:
        '''
        Setup the container data.
        The logic of delete.
        1. If the container_id is a pod, we delete the pod.
        2. If the container_id is a service, we delete the service.
        3. If the container_id is an ingress, we delete the ingress.
        4. We delete lingering resources.

        Cases for delete:
        ----------------
        1. Delete lingering ingress: Create 1 pod, 1 service and 1 ingresses. Delete the service.
            - The ingress should be deleted.
            - But the pod should not be deleted.
            - The namespace should not be deleted because the pod is still there.
        2. Delete lingering service: Create 2 pods and 1 service. Map service to only one pod.Delete the pod.
            -  The service should be deleted.
            - The namespace should not be deleted because one pod is still there.
        3. Non lingering ingress: Create 1 pods, 2 services and 1 ingress. Delete pod and one of the service.
            - The ingress should not be deleted, because it still has one service associated with it.
            - The namespace should not be deleted because 1 pod and 1 service are still there.
        4. Non lingering service: Create 2 pods and map them to same service.Delete one pod.
            - The service should not be deleted because it still has one pod associated with it.
            - The namespace should not be deleted because 1 pod and 1 service are still there.
        5. Delete all: 1 pod, 1 service and 1 ingress. Delete pod. Everything should be deleted. Because,
            - After pod is deleted, the service does not have any other pod, so it is deleted.
            - After service is deleted, the ingress does not have any other service, so it is deleted.
            - After ingress is deleted, the namespace does not have anything, so it is deleted as well.
        
        Cases that wont happen:
        ----------------------
        1. ContainerManager has a specific way of doing things.
        2. It will not bind multiple services to an ingress or multiple pods to a service.
        3. That can be done in resource manager, but not in container manager.
        4. In container manager, a pod is associated with at max only one service and,
            a service is associated with at max only one ingress.
        5. So here are the new cases:
            a. Pod, Service and Ingress are created. Service is deleted.
                - Deleted: Service, Ingress
                - Remaining: Pod, Namespace
            b. Pod, Service and Ingress are created. Ingress is deleted.
                - Deleted: Ingress
                - Remaining: Service, Pod, Namespace
            c. Pod, Service and Ingress are created. Pod is deleted.
                - Deleted: Pod, Service, Ingress, Namespace
                - Remaining: None
        
        Order of tests:
        ---------------
        1. Since deleting higher level resources like ingress/service
            might result in lingering lower level resources, the length of the resources might be affected.
            For example, deleting ingress might result in lingering service and pod.
            The next test checks the length of the service and pods, it will be 1 by default.
        2. So, here is the order:
            a. Delete pod.
            b. Delete service.
            c. Delete ingress.
        3. NOTE: container manager creates the namespace if it does not exist. So we dont need to worry about recreating
            the namespace after Delete pod test deletes everything.
        '''
        print('Test: setUp TestDeleteContainer')
        self.namespace_name: str = NAMESPACE_NAME
        self.image_name: str = 'zim95/ssh_ubuntu:latest'
        self.publish_information: list[PublishInformationDataClass] = [
            PublishInformationDataClass(publish_port=2222, target_port=22, protocol='TCP'),
        ]
        self.environment_variables: dict[str, str] = {
            'SSH_PASSWORD': '12345678',
            'SSH_USERNAME': 'test-user',
        }
        self.pod_container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=f'{self.container_name}-internal',
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=ExposureLevel.INTERNAL,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )
        self.service_container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=f'{self.container_name}-cluster-local',
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=ExposureLevel.CLUSTER_LOCAL,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )
        self.ingress_container_data: CreateContainerDataClass = CreateContainerDataClass(
            container_name=f'{self.container_name}-exposed',
            network_name=self.namespace_name,
            image_name=self.image_name,
            exposure_level=ExposureLevel.EXPOSED,
            publish_information=self.publish_information,
            environment_variables=self.environment_variables,
        )

    def test_a_delete_ingress(self) -> None:
        '''
        Create a container with an exposed exposure level.
        This creates: 1 pod, 1 service and 1 ingress.
        Delete the ingress.
        Result: The ingress is deleted. The pod and service remain and therefore the namespace remains.
        '''
        print('Test: test_delete_ingress')
        exposed_container: dict = KubernetesContainerManager.create(self.ingress_container_data)
        # list all resources
        initial_pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        initial_services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))
        initial_ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': self.namespace_name}))
        initial_namespaces: list = NamespaceManager.list()

        # assert the length of the resources
        self.assertEqual(len(initial_pods), 1)
        self.assertEqual(len(initial_services), 1)
        self.assertEqual(len(initial_ingresses), 1)
        self.assertEqual(NAMESPACE_NAME in [namespace['namespace_name'] for namespace in initial_namespaces], True)
        
        KubernetesContainerManager.delete(DeleteContainerDataClass(
            network_name=self.namespace_name,
            container_id=exposed_container['container_id'],
        ))
        # list all resources again
        final_pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        final_services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))
        final_ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': self.namespace_name}))
        final_namespaces: list = NamespaceManager.list()

        # assert the length of the resources
        self.assertEqual(len(final_pods), 0)  # one of the pod was deleted.
        self.assertEqual(len(final_services), 0)  # one of the service was deleted.
        self.assertEqual(len(final_ingresses), 0)  # the ingress was deleted.
        self.assertEqual(NAMESPACE_NAME in [namespace['namespace_name'] for namespace in final_namespaces], False)  # the namespace was not deleted.

    def test_b_delete_service(self) -> None:
        '''
        Create a container with an exposed exposure level.
        This creates: 1 pod, 1 service and 1 ingress.
        Delete the service.
        Result: The service is deleted. The ingress is also deleted. The pod remains and therefore the namespace remains.
        '''
        print('Test: test_delete_service')
        cluster_local_container: dict = KubernetesContainerManager.create(self.service_container_data)
        # list all resources
        initial_pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        initial_services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))
        initial_ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': self.namespace_name}))
        initial_namespaces: list = NamespaceManager.list()

        # assert the length of the resources
        self.assertEqual(len(initial_pods), 1)
        self.assertEqual(len(initial_services), 1)
        self.assertEqual(len(initial_ingresses), 0)
        self.assertEqual(NAMESPACE_NAME in [namespace['namespace_name'] for namespace in initial_namespaces], True)

        KubernetesContainerManager.delete(DeleteContainerDataClass(
            network_name=self.namespace_name,
            container_id=cluster_local_container['container_id'],
        ))
        # list all resources again
        final_pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        final_services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))
        final_ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': self.namespace_name}))
        final_namespaces: list = NamespaceManager.list()

        # assert the length of the resources
        self.assertEqual(len(final_pods), 0)  # one of the pod was deleted.
        self.assertEqual(len(final_services), 0)  # the service was deleted.
        self.assertEqual(len(final_ingresses), 0)  # the ingress was never there after the first test.
        self.assertEqual(NAMESPACE_NAME in [namespace['namespace_name'] for namespace in final_namespaces], False)  # the namespace was not deleted.

    def test_c_delete_pod(self) -> None:
        '''
        Create a container with an exposed exposure level.
        This creates: 1 pod, 1 service and 1 ingress.
        Delete the pod.
        Result: The pod is deleted. The service and ingress are also deleted. The namespace is also deleted.
        '''
        print('Test: test_delete_pod')
        internal_container: dict = KubernetesContainerManager.create(self.pod_container_data)
        # list all resources
        initial_pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        initial_services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))
        initial_ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': self.namespace_name}))
        initial_namespaces: list = NamespaceManager.list()

        # assert the length of the resources
        self.assertEqual(len(initial_pods), 1)
        self.assertEqual(len(initial_services), 0)
        self.assertEqual(len(initial_ingresses), 0)
        self.assertEqual(NAMESPACE_NAME in [namespace['namespace_name'] for namespace in initial_namespaces], True)

        KubernetesContainerManager.delete(DeleteContainerDataClass(
            network_name=self.namespace_name,
            container_id=internal_container['container_id'],
        ))
        # list all resources again
        final_pods: list = PodManager.list(ListPodDataClass(**{'namespace_name': self.namespace_name}))
        final_services: list = ServiceManager.list(ListServiceDataClass(**{'namespace_name': self.namespace_name}))
        final_ingresses: list = IngressManager.list(ListIngressDataClass(**{'namespace_name': self.namespace_name}))
        final_namespaces: list = NamespaceManager.list()

        # assert the length of the resources
        self.assertEqual(len(final_pods), 0)  # the pod was deleted.
        self.assertEqual(len(final_services), 0)  # the service was deleted.
        self.assertEqual(len(final_ingresses), 0)  # the ingress was deleted.
        self.assertEqual(NAMESPACE_NAME in [namespace['namespace_name'] for namespace in final_namespaces], False)  # the namespace was deleted.
