# builtins
from unittest import TestCase

# modules
from src.resources.resource_config import SNAPSHOT_JOB_IMAGE_NAME


class TestResourceConfig(TestCase):
    '''
    Unit test for resource_config constants. Does NOT require a cluster.
    '''

    def test_snapshot_job_image_uses_hyphen(self) -> None:
        print('Test: test_snapshot_job_image_uses_hyphen')
        # The image name must use a hyphen (snapshot-job), not an underscore.
        self.assertTrue(
            SNAPSHOT_JOB_IMAGE_NAME.endswith('/snapshot-job:latest'),
            f'Expected image name to end with /snapshot-job:latest, got {SNAPSHOT_JOB_IMAGE_NAME}'
        )
        self.assertNotIn('snapshot_job', SNAPSHOT_JOB_IMAGE_NAME)
