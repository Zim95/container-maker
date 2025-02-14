# built-ins
from unittest import TestCase
# modules
from src.common import config
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.dataclasses.volume.create_volume_dataclass import CreateVolumeDataClass, VolumeAccessMode, VolumeReclaimPolicy
from src.resources.dataclasses.volume.delete_volume_dataclass import DeleteVolumeDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.volume_manager import VolumeManager


NAMESPACE_NAME: str = 'test-volume-namespace'


class TestVolumeManager(TestCase):
    def setUp(self) -> None:
        self.namespace_name: str = NAMESPACE_NAME
        NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': self.namespace_name}))

        self.create_volume_data: CreateVolumeDataClass = CreateVolumeDataClass(
            **{
                'namespace_name': self.namespace_name,
                'volume_name': 'test-volume',
                'nfs_server': config.NFS_IP,
                'nfs_path': config.NFS_PATH,
            }
        )

    def test_creation_and_removal_of_volume(self) -> None:
        '''
        Test the creation and removal of volume
        '''
        print('Test: test_creation_and_removal_of_volume')
        volume: dict = VolumeManager.create(self.create_volume_data)
        self.assertIsNotNone(volume)

        # check for volume, claim names and namespace
        self.assertEqual(volume['volume']['volume_name'], self.create_volume_data.volume_name)
        self.assertEqual(volume['claim']['claim_name'], f'{self.create_volume_data.volume_name}-claim')
        self.assertEqual(volume['claim']['claim_namespace'], self.namespace_name)
        self.assertEqual(volume['volume']['volume_nfs_server'], self.create_volume_data.nfs_server)
        self.assertEqual(volume['volume']['volume_nfs_path'], self.create_volume_data.nfs_path)

        # check for volume default values
        self.assertEqual(volume['volume']['volume_access_modes'], [VolumeAccessMode.READ_WRITE_ONCE.value])
        self.assertEqual(volume['volume']['volume_reclaim_policy'], VolumeReclaimPolicy.DELETE.value)
        self.assertEqual(volume['volume']['volume_size'], '1Gi')

    def test_creation_and_removal_of_duplicate_volume(self) -> None:
        '''
        Test the creation and removal of duplicate volumes.
        Result: Should not create the second volume. It should return the first volume.
        '''
        print('Test: test_creation_and_removal_of_duplicate_volume')
        first_volume: dict = VolumeManager.create(self.create_volume_data)

        # check for volume, claim names and namespace
        self.assertEqual(first_volume['volume']['volume_name'], self.create_volume_data.volume_name)
        self.assertEqual(first_volume['claim']['claim_name'], f'{self.create_volume_data.volume_name}-claim')
        self.assertEqual(first_volume['claim']['claim_namespace'], self.namespace_name)
        self.assertEqual(first_volume['volume']['volume_nfs_server'], self.create_volume_data.nfs_server)
        self.assertEqual(first_volume['volume']['volume_nfs_path'], self.create_volume_data.nfs_path)
        # check for volume default values
        self.assertEqual(first_volume['volume']['volume_access_modes'], [VolumeAccessMode.READ_WRITE_ONCE.value])
        self.assertEqual(first_volume['volume']['volume_reclaim_policy'], VolumeReclaimPolicy.DELETE.value)
        self.assertEqual(first_volume['volume']['volume_size'], '1Gi')
        

        second_volume: dict = VolumeManager.create(self.create_volume_data)

        # check for volume, claim names and namespace
        self.assertEqual(second_volume['volume']['volume_name'], self.create_volume_data.volume_name)
        self.assertEqual(second_volume['claim']['claim_name'], f'{self.create_volume_data.volume_name}-claim')
        self.assertEqual(second_volume['claim']['claim_namespace'], self.namespace_name)
        self.assertEqual(second_volume['volume']['volume_nfs_server'], self.create_volume_data.nfs_server)
        self.assertEqual(second_volume['volume']['volume_nfs_path'], self.create_volume_data.nfs_path)

        # check for volume default values
        self.assertEqual(second_volume['volume']['volume_access_modes'], [VolumeAccessMode.READ_WRITE_ONCE.value])
        self.assertEqual(second_volume['volume']['volume_reclaim_policy'], VolumeReclaimPolicy.DELETE.value)
        self.assertEqual(second_volume['volume']['volume_size'], '1Gi')

        # make sure the ids and the names are the same
        assert first_volume['volume']['volume_id'] == second_volume['volume']['volume_id']
        assert first_volume['volume']['volume_name'] == second_volume['volume']['volume_name']
        assert first_volume['claim']['claim_id'] == second_volume['claim']['claim_id']
        assert first_volume['claim']['claim_name'] == second_volume['claim']['claim_name']
        assert first_volume['claim']['claim_namespace'] == second_volume['claim']['claim_namespace']

    def test_volume_size(self) -> None:
        '''
        Test if storage size is configurable.
        '''
        print('Test: test_volume_size')
        self.create_volume_data.storage_size = '2Gi'
        volume: dict = VolumeManager.create(self.create_volume_data)

        # check for volume, claim names and namespace
        self.assertEqual(volume['volume']['volume_name'], self.create_volume_data.volume_name)
        self.assertEqual(volume['claim']['claim_name'], f'{self.create_volume_data.volume_name}-claim')
        self.assertEqual(volume['claim']['claim_namespace'], self.namespace_name)
        self.assertEqual(volume['volume']['volume_nfs_server'], self.create_volume_data.nfs_server)
        self.assertEqual(volume['volume']['volume_nfs_path'], self.create_volume_data.nfs_path)
        # check for volume default values
        self.assertEqual(volume['volume']['volume_access_modes'], [VolumeAccessMode.READ_WRITE_ONCE.value])
        self.assertEqual(volume['volume']['volume_reclaim_policy'], VolumeReclaimPolicy.DELETE.value)
        self.assertEqual(volume['volume']['volume_size'], '2Gi')  # this is what we are testing

    def test_volume_access_modes(self) -> None:
        '''
        Test if access modes are configurable.
        '''
        print('Test: test_volume_access_modes')
        self.create_volume_data.access_modes = [VolumeAccessMode.READ_ONLY_MANY]
        volume: dict = VolumeManager.create(self.create_volume_data)

        # check for volume, claim names and namespace
        self.assertEqual(volume['volume']['volume_name'], self.create_volume_data.volume_name)
        self.assertEqual(volume['claim']['claim_name'], f'{self.create_volume_data.volume_name}-claim')
        self.assertEqual(volume['claim']['claim_namespace'], self.namespace_name)
        self.assertEqual(volume['volume']['volume_nfs_server'], self.create_volume_data.nfs_server)
        self.assertEqual(volume['volume']['volume_nfs_path'], self.create_volume_data.nfs_path)
        # check for volume default values
        self.assertEqual(volume['volume']['volume_access_modes'], [VolumeAccessMode.READ_ONLY_MANY.value])  # this is what we are testing
        self.assertEqual(volume['volume']['volume_reclaim_policy'], VolumeReclaimPolicy.DELETE.value)
        self.assertEqual(volume['volume']['volume_size'], '1Gi')

    def test_volume_reclaim_policy(self) -> None:
        '''
        Test if reclaim policy is configurable.
        '''
        print('Test: test_volume_reclaim_policy')
        self.create_volume_data.reclaim_policy = VolumeReclaimPolicy.RETAIN
        volume: dict = VolumeManager.create(self.create_volume_data)

        # check for volume, claim names and namespace
        self.assertEqual(volume['volume']['volume_name'], self.create_volume_data.volume_name)
        self.assertEqual(volume['claim']['claim_name'], f'{self.create_volume_data.volume_name}-claim')
        self.assertEqual(volume['claim']['claim_namespace'], self.namespace_name)
        self.assertEqual(volume['volume']['volume_nfs_server'], self.create_volume_data.nfs_server)
        self.assertEqual(volume['volume']['volume_nfs_path'], self.create_volume_data.nfs_path)
        # check for volume default values
        self.assertEqual(volume['volume']['volume_access_modes'], [VolumeAccessMode.READ_WRITE_ONCE.value])
        self.assertEqual(volume['volume']['volume_reclaim_policy'], VolumeReclaimPolicy.RETAIN.value)  # this is what we are testing
        self.assertEqual(volume['volume']['volume_size'], '1Gi')

    def tearDown(self) -> None:
        print('Teardown: test_volume_manager')
        # adding deletion in teardown is important. Because, even if the test fails in between, the volume is cleanedup.
        VolumeManager.delete(
            DeleteVolumeDataClass(
                **{'namespace_name': self.namespace_name, 'volume_name': self.create_volume_data.volume_name}
            )
        )


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        '''
        Delete the namespace.
        '''
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': NAMESPACE_NAME}))
