# builtins
import time
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client import V1Pod, V1ObjectMeta, V1PodStatus, V1PodSpec

# modules
from src.resources.pod_manager import PodManager
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass


class TestPodResponseDoesNotBlockOnMissingIP(TestCase):
    '''
    Regression test for a real production bug: get_pod_response used to resolve pod_ip via a
    fresh, blocking API call (get_pod_ip) that waits up to POD_IP_TIMEOUT_SECONDS and then RAISES
    if the pod never got an IP - even though list()/get() already have the pod object in hand and
    only create() actually needs to guarantee an IP before returning. Caught live: a single pod
    stuck in ContainerCreating (an unrelated sandbox-runtime failure) made every list()-backed
    lookup in its namespace fail, including the DELETE path's own pod lookup - so the one
    operation you'd most want to work on a broken pod (delete it) failed too, with "Timeout
    waiting for pod ... IP address after 20.0 seconds".
    '''

    def test_list_returns_immediately_for_a_pod_with_no_ip_yet(self) -> None:
        pod_no_ip = V1Pod(
            metadata=V1ObjectMeta(name="stuck-pod", namespace="ns-1", uid="uid-1", labels={}),
            status=V1PodStatus(pod_ip=None),
            spec=V1PodSpec(containers=[]),
        )
        mock_client = MagicMock()
        mock_client.list_namespaced_pod.return_value.items = [pod_no_ip]

        with patch.object(PodManager, "client", mock_client), \
             patch.object(PodManager, "check_kubernetes_client", return_value=None):
            start = time.monotonic()
            result = PodManager.list(ListPodDataClass(namespace_name="ns-1"))
            elapsed = time.monotonic() - start

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["pod_ip"], "")
        self.assertLess(elapsed, 1.0, "list() must not block waiting for a pod's IP")
        mock_client.read_namespaced_pod.assert_not_called()

    def test_list_does_not_fail_the_whole_namespace_when_one_pod_has_no_ip(self) -> None:
        '''The exact bug: a healthy pod's lookup must not be collateral damage from a broken
        sibling pod (or itself) still lacking an IP in the same namespace.'''
        stuck_pod = V1Pod(
            metadata=V1ObjectMeta(name="stuck-pod", namespace="ns-1", uid="uid-1", labels={}),
            status=V1PodStatus(pod_ip=None),
            spec=V1PodSpec(containers=[]),
        )
        healthy_pod = V1Pod(
            metadata=V1ObjectMeta(name="healthy-pod", namespace="ns-1", uid="uid-2", labels={}),
            status=V1PodStatus(pod_ip="10.42.0.5"),
            spec=V1PodSpec(containers=[]),
        )
        mock_client = MagicMock()
        mock_client.list_namespaced_pod.return_value.items = [stuck_pod, healthy_pod]

        with patch.object(PodManager, "client", mock_client), \
             patch.object(PodManager, "check_kubernetes_client", return_value=None):
            result = PodManager.list(ListPodDataClass(namespace_name="ns-1"))

        self.assertEqual(len(result), 2)
        self.assertEqual(result[1]["pod_ip"], "10.42.0.5")


class TestCreateStillWaitsForIP(TestCase):
    '''create() is the one caller that genuinely needs a populated IP before returning - it must
    keep doing so explicitly now that get_pod_response itself no longer blocks.'''

    def test_create_calls_get_pod_ip_and_rereads_the_pod_before_returning(self) -> None:
        from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass, ResourceRequirementsDataClass

        data = CreatePodDataClass(
            image_name="myrepo/ssh_ubuntu:latest", pod_name="testc-pod-123", container_name="testc",
            namespace_name="ns-1", target_ports={22}, environment_variables={},
            resource_requirements=ResourceRequirementsDataClass(),
        )
        fresh_pod_with_ip = V1Pod(
            metadata=V1ObjectMeta(name="testc-pod-123", namespace="ns-1", uid="uid-1", labels={}),
            status=V1PodStatus(pod_ip="10.42.0.9"),
            spec=V1PodSpec(containers=[]),
        )
        mock_client = MagicMock()
        mock_client.read_namespaced_pod.return_value = fresh_pod_with_ip

        with patch.object(PodManager, "client", mock_client), \
             patch.object(PodManager, "check_kubernetes_client", return_value=None), \
             patch.object(PodManager, "get", return_value={}), \
             patch.object(PodManager, "poll_status", return_value=None), \
             patch.object(PodManager, "get_pod_ip", return_value="10.42.0.9") as mock_get_ip:
            result = PodManager.create(data)

        mock_get_ip.assert_called_once_with("ns-1", "testc-pod-123")
        self.assertEqual(result["pod_ip"], "10.42.0.9")
