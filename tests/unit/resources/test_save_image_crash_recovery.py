# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.pod_manager import SaveUtility
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass


class TestSaveImageCrashRecoveryWiring(TestCase):
    '''
    UNIT test (no cluster): SaveUtility.save_image is the crash-recovery seam. After the
    snapshot Job completes it must point the pod's MAIN container at the saved image via
    PodManager._update_pod_image, so a crashed container is restarted in place from the
    snapshot. We mock the client check, tar build, JobManager, and _update_pod_image, and
    assert the wiring plus the exact repo-prefixed image name.
    '''

    def setUp(self) -> None:
        print('Test: setUp TestSaveImageCrashRecoveryWiring')
        self.namespace_name: str = 'test-namespace'
        self.pod_name: str = 'testc-pod-123'
        self.data: SavePodDataClass = SavePodDataClass(
            pod_name=self.pod_name,
            namespace_name=self.namespace_name,
            environment_variables={
                'CONTAINER_ID': 'db-id-1',
                'DB_HOST': 'h', 'DB_PORT': '5432',
                'DB_USERNAME': 'u', 'DB_PASSWORD': 'p', 'DB_DATABASE': 'd',
            },
        )

    def _invoke(self):
        mock_update = MagicMock(return_value=None)
        with patch.object(SaveUtility, 'check_kubernetes_client', return_value=None), \
             patch.object(SaveUtility, 'build_tar', return_value='snapshots/testc-pod-123'), \
             patch('src.resources.pod_manager.REPO_NAME', 'myrepo'), \
             patch('src.resources.pod_manager.REPO_PASSWORD', 'secret'), \
             patch('src.resources.job_manager.JobManager.create_snapshot_job',
                   return_value={'namespace_name': self.namespace_name,
                                 'job_name': f'{self.pod_name}-snapshot-job'}), \
             patch('src.resources.job_manager.JobManager.wait_for_job_completion',
                   return_value={'status': 'succeeded'}), \
             patch('src.resources.pod_manager.PodManager._update_pod_image', mock_update):
            result: dict = SaveUtility.save_image(self.data)
        return result, mock_update

    def test_returns_repo_prefixed_saved_image(self) -> None:
        print('Test: test_returns_repo_prefixed_saved_image')
        result, _ = self._invoke()
        self.assertEqual(result['image_name'], f'myrepo/{self.pod_name}-image:latest')

    def test_points_main_container_at_saved_image_for_crash_recovery(self) -> None:
        print('Test: test_points_main_container_at_saved_image_for_crash_recovery')
        _, mock_update = self._invoke()
        mock_update.assert_called_once()
        kwargs = mock_update.call_args.kwargs
        self.assertEqual(kwargs['namespace_name'], self.namespace_name)
        self.assertEqual(kwargs['pod_name'], self.pod_name)
        self.assertEqual(kwargs['image_name'], f'myrepo/{self.pod_name}-image:latest')
