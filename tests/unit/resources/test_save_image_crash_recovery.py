# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.resources.pod_manager import SaveUtility
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass


class _SyncThread:
    '''
    Stand-in for threading.Thread that runs its target synchronously on .start(). save_image
    hands the wait-then-patch-pod-image work to a real background thread in production (so it
    doesn't hold a gRPC worker thread for the save's whole duration -- see progress_made.md's
    "gRPC worker thread exhaustion" finding); in tests we don't want real thread-timing races,
    so this fake runs the same target inline and lets us assert on the result deterministically.
    '''

    def __init__(self, target=None, args=(), kwargs=None, daemon=None, name=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self):
        self._target(*self._args, **self._kwargs)


class TestSaveImageCrashRecoveryWiring(TestCase):
    '''
    UNIT test (no cluster): SaveUtility.save_image creates the snapshot Job and returns
    immediately with the (deterministic, repo-prefixed) image name -- it does NOT block on Job
    completion. The wait-then-patch-pod-image work (SaveUtility._wait_and_patch_pod_image) is
    handed to its own background thread instead, so it must point the pod's MAIN container at
    the saved image via PodManager._update_pod_image once the Job succeeds, and must swallow
    (not re-raise) a Job failure without patching -- there is no caller to raise to, and Job
    failure is already recorded in the DB by the Job itself or the save reconciler. We mock the
    client check, tar build, JobManager, and _update_pod_image throughout, and stand in for
    threading.Thread with a synchronous fake so assertions don't race a real thread.
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

    def _invoke(self, wait_side_effect=None):
        mock_update = MagicMock(return_value=None)
        mock_wait = MagicMock(return_value={'status': 'succeeded'}, side_effect=wait_side_effect)
        with patch.object(SaveUtility, 'check_kubernetes_client', return_value=None), \
             patch.object(SaveUtility, 'build_tar', return_value='snapshots/testc-pod-123'), \
             patch('src.resources.pod_manager.REPO_NAME', 'myrepo'), \
             patch('src.resources.pod_manager.REPO_PASSWORD', 'secret'), \
             patch('src.resources.pod_manager.threading.Thread', _SyncThread), \
             patch('src.resources.job_manager.JobManager.create_snapshot_job',
                   return_value={'namespace_name': self.namespace_name,
                                 'job_name': f'{self.pod_name}-snapshot-job'}), \
             patch('src.resources.job_manager.JobManager.wait_for_job_completion', mock_wait), \
             patch('src.resources.pod_manager.PodManager._update_pod_image', mock_update):
            result: dict = SaveUtility.save_image(self.data)
        return result, mock_update, mock_wait

    def test_returns_repo_prefixed_saved_image(self) -> None:
        print('Test: test_returns_repo_prefixed_saved_image')
        result, _, _ = self._invoke()
        self.assertEqual(result['image_name'], f'myrepo/{self.pod_name}-image:latest')

    def test_points_main_container_at_saved_image_for_crash_recovery(self) -> None:
        print('Test: test_points_main_container_at_saved_image_for_crash_recovery')
        _, mock_update, _ = self._invoke()
        mock_update.assert_called_once()
        kwargs = mock_update.call_args.kwargs
        self.assertEqual(kwargs['namespace_name'], self.namespace_name)
        self.assertEqual(kwargs['pod_name'], self.pod_name)
        self.assertEqual(kwargs['image_name'], f'myrepo/{self.pod_name}-image:latest')

    def test_skips_pod_image_patch_when_job_fails(self) -> None:
        '''If the Job fails/times out, the background finalize step must swallow the exception
        (nothing to raise it to -- it's a thread target) and must NOT patch the pod's image.
        Save failure is already/will be recorded in the DB by the Job itself or the save
        reconciler, so there is nothing else for this thread to do beyond logging.'''
        print('Test: test_skips_pod_image_patch_when_job_fails')
        _, mock_update, mock_wait = self._invoke(wait_side_effect=Exception('job failed'))
        mock_wait.assert_called_once()
        mock_update.assert_not_called()


class TestWaitAndPatchPodImage(TestCase):
    '''
    UNIT test (no cluster): SaveUtility._wait_and_patch_pod_image directly, bypassing
    save_image/threading entirely -- exercises the finalize step's own logic in isolation.
    '''

    def test_waits_then_patches_on_success(self) -> None:
        print('Test: test_waits_then_patches_on_success')
        mock_wait = MagicMock(return_value={'status': 'succeeded'})
        mock_update = MagicMock(return_value=None)
        with patch('src.resources.job_manager.JobManager.wait_for_job_completion', mock_wait), \
             patch('src.resources.pod_manager.PodManager._update_pod_image', mock_update):
            SaveUtility._wait_and_patch_pod_image(
                job_namespace='browseterm', job_name='some-job',
                pod_namespace='ns', pod_name='pod-1', image_name='repo/pod-1-image:latest',
            )
        mock_wait.assert_called_once_with(namespace_name='browseterm', job_name='some-job')
        mock_update.assert_called_once_with(
            namespace_name='ns', pod_name='pod-1', image_name='repo/pod-1-image:latest',
        )

    def test_swallows_wait_failure_without_patching(self) -> None:
        print('Test: test_swallows_wait_failure_without_patching')
        mock_update = MagicMock(return_value=None)
        with patch('src.resources.job_manager.JobManager.wait_for_job_completion',
                   side_effect=Exception('job failed')), \
             patch('src.resources.pod_manager.PodManager._update_pod_image', mock_update):
            # must not raise -- there is no caller to catch it, this runs as a thread target
            SaveUtility._wait_and_patch_pod_image(
                job_namespace='browseterm', job_name='some-job',
                pod_namespace='ns', pod_name='pod-1', image_name='repo/pod-1-image:latest',
            )
        mock_update.assert_not_called()
