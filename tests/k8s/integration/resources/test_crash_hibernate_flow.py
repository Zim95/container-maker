'''
REAL integration tests (live cluster, run IN-CLUSTER only) for the two workspace-lifecycle
flows, behaviour-first: create a pod + service pair, then exercise the flow and check the pod
still works.

  1. save -> crash -> resume (in-place crash recovery): create a pod+service pair, crash the
     main container, wait, and assert the pod recovered (main container Ready again) and the
     service still routes to it.
  2. save -> hibernate -> resume: create a pod+service pair, save it, delete the pod (hibernate),
     recreate the pod from the saved image (resume), wait, and assert the pod is Running and the
     service still routes to it.

Namespace convention (mirrors test_pod_manager.py / test_service_manager.py): one namespace for
this module, created idempotently in setUp; the pod + service are deleted in tearDown; the
namespace is deleted only by the trailing ZZZ_Cleanup suite (its name sorts last).

PRECONDITIONS (in-cluster only): these call PodManager/ServiceManager/ExecUtility which use the
in-cluster k8s client (KubernetesResourceManager). From a dev host client is None and every call
raises UnsupportedRuntimeEnvironment, so the suite runs only inside the cluster (same as the rest
of tests/k8s/integration/*). The hibernate flow additionally needs the snapshot-Job infra +
registry push/pull creds so the saved image can be built, pushed, and pulled back on resume.
'''

# builtins
from unittest import TestCase
import time

# modules
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass, ResourceRequirementsDataClass
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.get_pod_dataclass import GetPodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.resources.dataclasses.service.create_service_dataclass import (
    CreateServiceDataClass, PublishInformationDataClass,
)
from src.resources.dataclasses.service.delete_service_dataclass import DeleteServiceDataClass
from src.resources.dataclasses.service.get_service_dataclass import GetServiceDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.pod_manager import PodManager, ExecUtility
from src.resources.service_manager import ServiceManager
from src.common.config import REPO_NAME
from src.resources.resource_config import POD_UPTIME_TIMEOUT, CONTAINER_READINESS_TIMEOUT_SECONDS


NAMESPACE_NAME: str = 'test-crash-hibernate-flow'


def _fixtures(self, pod_name: str, service_name: str) -> None:
    '''
    Build a pod + service pair fixture (same shape as test_service_manager.py) and create the
    namespace. The service selects the pod by container_name (the label selector).
    '''
    self.image_name: str = f'{REPO_NAME}/ssh_ubuntu:latest'
    self.pod_name: str = pod_name
    self.container_name: str = f'{pod_name}-c'   # label selector, no timestamp
    self.service_name: str = service_name
    self.namespace_name: str = NAMESPACE_NAME
    self.target_ports: set = {22}
    self.environment_variables: dict = {
        'SSH_USERNAME': 'ubuntu',
        'SSH_PASSWORD': 'testpwd',
        'CONTAINER_ID': '1234567890',
        'DB_HOST': 'testhost', 'DB_PORT': '5432',
        'DB_USERNAME': 'testuser', 'DB_PASSWORD': 'testpassword', 'DB_DATABASE': 'testdatabase',
    }
    self.resource_requirements: ResourceRequirementsDataClass = ResourceRequirementsDataClass()
    self.create_pod_data: CreatePodDataClass = CreatePodDataClass(
        image_name=self.image_name,
        pod_name=self.pod_name,
        container_name=self.container_name,
        namespace_name=self.namespace_name,
        target_ports=self.target_ports,
        environment_variables=self.environment_variables,
        resource_requirements=self.resource_requirements,
    )
    self.create_service_data: CreateServiceDataClass = CreateServiceDataClass(
        service_name=self.service_name,
        pod_label_selector=self.container_name,
        namespace_name=self.namespace_name,
        publish_information=[
            PublishInformationDataClass(publish_port=2222, target_port=22, protocol='TCP'),
        ],
    )
    self.save_pod_data: SavePodDataClass = SavePodDataClass(
        pod_name=self.pod_name,
        namespace_name=self.namespace_name,
        environment_variables={
            'CONTAINER_ID': '1234567890',
            'DB_HOST': 'testhost', 'DB_PORT': '5432',
            'DB_USERNAME': 'testuser', 'DB_PASSWORD': 'testpassword', 'DB_DATABASE': 'testdatabase',
        },
    )
    NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))


def _delete_pair(self) -> None:
    '''Best-effort teardown of the pod + service (namespace is cleaned by ZZZ_Cleanup).'''
    try:
        ServiceManager.delete(DeleteServiceDataClass(**{
            'namespace_name': self.namespace_name, 'service_name': self.service_name}))
    except Exception as e:
        print(f'service delete (ignored): {e}')
    try:
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name, 'pod_name': self.pod_name}))
    except Exception as e:
        print(f'pod delete (ignored): {e}')


class TestCrashRecoveryFlow(TestCase):
    '''
    save -> crash -> resume: create a pod + service pair, crash the main container, wait, and
    assert the pod recovered and the service still routes to it. Crash recovery is the kubelet
    restarting the main container in place (restartPolicy defaults to Always), so no explicit
    resume step is needed.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestCrashRecoveryFlow')
        _fixtures(self, pod_name='test-crash-pod', service_name='test-crash-service')
        PodManager.create(self.create_pod_data)
        ServiceManager.create(self.create_service_data)

    def test_a_pod_recovers_after_crash(self) -> None:
        print('Test: test_a_pod_recovers_after_crash')
        # sanity: the pod is up and the service routes to exactly one pod before we crash it.
        PodManager.poll_container_readiness(
            namespace_name=self.namespace_name, pod_name=self.pod_name,
            container_names=[self.pod_name], timeout_seconds=CONTAINER_READINESS_TIMEOUT_SECONDS)
        svc_before: dict = ServiceManager.get(GetServiceDataClass(**{
            'namespace_name': self.namespace_name, 'service_name': self.service_name}))
        self.assertNotEqual(svc_before, {})

        # crash: SIGKILL everything but PID 1 -> sshd dies -> entrypoint exits -> kubelet restarts
        # the main container. The exec socket dies with the container, so ignore its error.
        try:
            ExecUtility.run_command(self.pod_name, self.namespace_name, self.pod_name, 'kill -9 -1')
        except Exception as e:
            print(f'crash exec ended (expected): {e}')

        # wait a moment for the kubelet to notice the exit, then wait for the pod to work again.
        time.sleep(5)
        PodManager.poll_container_readiness(
            namespace_name=self.namespace_name, pod_name=self.pod_name,
            container_names=[self.pod_name], timeout_seconds=POD_UPTIME_TIMEOUT)

        # the pod worked: it's Running again and the service still routes to it.
        pod_after: dict = PodManager.get(GetPodDataClass(**{
            'namespace_name': self.namespace_name, 'pod_name': self.pod_name}))
        self.assertNotEqual(pod_after, {})
        svc_after: dict = ServiceManager.get(GetServiceDataClass(**{
            'namespace_name': self.namespace_name, 'service_name': self.service_name}))
        self.assertNotEqual(svc_after, {})
        self.assertTrue(len(svc_after.get('associated_resources', [])) >= 1)

    def tearDown(self) -> None:
        print('Test: tearDown TestCrashRecoveryFlow')
        _delete_pair(self)


class TestHibernateResumeFlow(TestCase):
    '''
    save -> hibernate -> resume: create a pod + service pair, save it, delete the pod (hibernate),
    recreate the pod from the saved image (resume), wait, and assert the pod is Running and the
    service still routes to it.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestHibernateResumeFlow')
        _fixtures(self, pod_name='test-hib-pod', service_name='test-hib-service')
        PodManager.create(self.create_pod_data)
        ServiceManager.create(self.create_service_data)

    def test_a_pod_works_after_hibernate_resume(self) -> None:
        print('Test: test_a_pod_works_after_hibernate_resume')
        PodManager.poll_container_readiness(
            namespace_name=self.namespace_name, pod_name=self.pod_name,
            container_names=[self.pod_name], timeout_seconds=CONTAINER_READINESS_TIMEOUT_SECONDS)

        # save: snapshot the workspace and capture the saved image name to resume from.
        save_result: dict = PodManager.save(self.save_pod_data)
        saved_image: str = save_result['image_name']
        self.assertEqual(saved_image, f'{REPO_NAME}/{self.pod_name}-image:latest')

        # hibernate: delete the pod (poll_termination blocks until it's gone). The service stays.
        PodManager.delete(DeletePodDataClass(**{
            'namespace_name': self.namespace_name, 'pod_name': self.pod_name}))
        self.assertEqual(PodManager.get(GetPodDataClass(**{
            'namespace_name': self.namespace_name, 'pod_name': self.pod_name})), {})

        # resume: recreate the pod from the saved image (same labels, so the surviving service
        # routes to it again).
        resume_pod_data: CreatePodDataClass = CreatePodDataClass(
            image_name=saved_image,
            pod_name=self.pod_name,
            container_name=self.container_name,
            namespace_name=self.namespace_name,
            target_ports=self.target_ports,
            environment_variables=self.environment_variables,
            resource_requirements=self.resource_requirements,
        )
        PodManager.create(resume_pod_data)

        # wait, then assert the pod worked and the service routes to the resumed pod.
        PodManager.poll_container_readiness(
            namespace_name=self.namespace_name, pod_name=self.pod_name,
            container_names=[self.pod_name], timeout_seconds=POD_UPTIME_TIMEOUT)
        svc_after: dict = ServiceManager.get(GetServiceDataClass(**{
            'namespace_name': self.namespace_name, 'service_name': self.service_name}))
        self.assertNotEqual(svc_after, {})
        self.assertTrue(len(svc_after.get('associated_resources', [])) >= 1)

    def tearDown(self) -> None:
        print('Test: tearDown TestHibernateResumeFlow')
        _delete_pair(self)


class ZZZ_Cleanup(TestCase):
    '''Runs last (name sorts after the flow suites): remove the shared namespace.'''

    def test_cleanup(self) -> None:
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
