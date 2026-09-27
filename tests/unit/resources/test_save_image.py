# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.pod_manager import SaveUtility, PodManager
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass


class TestSaveImage(TestCase):
    '''
    UNIT test (no cluster): fixed 2026-09-27. SaveUtility.save_image used to also hand a
    wait-then-patch-the-live-pod's-image job off to a background thread once the snapshot Job
    succeeded ("in-place crash recovery") - removed, because Kubernetes restarts a container the
    instant its live spec.image changes, which made every single Save disrupt the session it was
    meant to snapshot WITHOUT stopping. Now that crashes are handled by
    restart_policy=Never + status_monitor's skip-save Hibernate -> Resume path instead (see
    test_create_pod_restart_policy.py), save_image must ONLY create the snapshot Job and return -
    it must never spawn a thread, and must never touch the live pod at all.
    '''

    def setUp(self) -> None:
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'testc-pod-123'
        self.data: SavePodDataClass = SavePodDataClass(
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            environment_variables={'CONTAINER_ID': 'db-id-1'},
        )

    def test_save_image_never_touches_the_live_pod(self) -> None:
        mock_patch_pod = MagicMock()
        with patch.object(SaveUtility, 'check_kubernetes_client', return_value=None), \
             patch.object(SaveUtility, 'build_tar', return_value='snapshots/testc-pod-123'), \
             patch('src.resources.pod_manager.REPO_NAME', 'myrepo'), \
             patch('src.resources.pod_manager.REPO_PASSWORD', 'secret'), \
             patch('src.resources.job_manager.JobManager.create_snapshot_job',
                   return_value={'namespace_name': self.namespace_name,
                                 'job_name': f'{self.pod_name}-snapshot-job'}), \
             patch.object(PodManager, 'client', mock_patch_pod):
            result: dict = SaveUtility.save_image(self.data)

        # No pod mutation of any kind - patch_namespaced_pod (or anything else) on the
        # Kubernetes client is never called from save_image.
        mock_patch_pod.patch_namespaced_pod.assert_not_called()
        self.assertEqual(result['image_name'], f'myrepo/{self.pod_name}-image:latest')
        self.assertEqual(result['job_name'], f'{self.pod_name}-snapshot-job')
        self.assertEqual(result['job_namespace_name'], self.namespace_name)

    def test_save_image_does_not_reference_threading(self) -> None:
        '''Regression guard: the old background-thread finalize step (and the module-level
        `threading` import it needed) must stay gone, not just unused-but-present.'''
        import src.resources.pod_manager as pod_manager_module
        self.assertFalse(hasattr(pod_manager_module, 'threading'))
        self.assertFalse(hasattr(SaveUtility, '_wait_and_patch_pod_image'))
        self.assertFalse(hasattr(PodManager, '_update_pod_image'))
