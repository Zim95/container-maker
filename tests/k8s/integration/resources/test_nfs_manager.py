from unittest import TestCase
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.nfs.create_nfs_dataclass import CreateNFSDataClass
from src.resources.dataclasses.nfs.delete_nfs_dataclass import DeleteNFSDataClass
from src.resources.dataclasses.nfs.list_nfs_dataclass import ListNFSDataClass
from src.resources.nfs_manager import NFSManager


NAMESPACE_NAME: str = 'test-nfs-manager'


class TestNFSManager(TestCase):

    def setUp(self) -> None:
        """
        Create a namespace.
        """
        print('Setup: setUp')
        self.nfs_name: str = 'test-nfs'
        self.namespace_name: str = NAMESPACE_NAME
        NamespaceManager.create(CreateNamespaceDataClass(namespace_name=self.namespace_name))

    def test_creation_and_removal_of_nfs(self) -> None:
        """
        Test the creation of NFS and its removal.
        Runs: list, create and delete methods to test behavior.
        """
        print('Test: test_creation_and_removal_of_nfs')

        # List all NFS -> should return empty.
        nfs_old: list[dict] = NFSManager.list(ListNFSDataClass(namespace_name=self.namespace_name))
        assert nfs_old == []

        # Create an NFS
        nfs: dict = NFSManager.create(CreateNFSDataClass(
            namespace_name=self.namespace_name,
            nfs_name=self.nfs_name
        ))

        # Verify NFS properties
        self.assertEqual(nfs['nfs_name'], self.nfs_name)
        self.assertEqual(nfs['nfs_namespace'], self.namespace_name)
        self.assertEqual(nfs['nfs_ip'] is not None, True)

        # List all NFS -> should have a list.
        nfs_new: list[dict] = NFSManager.list(ListNFSDataClass(namespace_name=self.namespace_name))
        assert len(nfs_new) == 1

        # Delete the NFS -> cleanup.
        NFSManager.delete(DeleteNFSDataClass(namespace_name=self.namespace_name, nfs_name=self.nfs_name))
        nfs_last: list[dict] = NFSManager.list(ListNFSDataClass(namespace_name=self.namespace_name))
        assert nfs_last == []

    def test_duplicate_nfs_creation(self) -> None:
        """
        Test the creation of an NFS with the same name as an existing NFS.
        Result: Should return the existing NFS instead of creating a duplicate.
        """
        print('Test: test_duplicate_nfs_creation')

        # Create first NFS and get its UID
        first_nfs = NFSManager.create(CreateNFSDataClass(namespace_name=self.namespace_name, nfs_name=self.nfs_name))
        first_uid = first_nfs['nfs_id']
        self.assertEqual(first_nfs['nfs_ip'] is not None, True)

        # Try to create "duplicate" NFS
        second_nfs = NFSManager.create(CreateNFSDataClass(namespace_name=self.namespace_name, nfs_name=self.nfs_name))
        second_uid = second_nfs['nfs_id']
        self.assertEqual(second_nfs['nfs_ip'] is not None, True)

        # Verify it's the same NFS (ids should match)
        assert first_uid == second_uid

        # Verify only one NFS exists
        nfs_list: list[dict] = NFSManager.list(ListNFSDataClass(namespace_name=self.namespace_name))
        assert len(nfs_list) == 1

        # Cleanup
        NFSManager.delete(DeleteNFSDataClass(namespace_name=self.namespace_name, nfs_name=self.nfs_name))


class ZZZ_Cleanup(TestCase):

    def test_cleanup(self) -> None:
        """
        Delete the namespace.
        """
        print('Cleanup: test_cleanup')
        NamespaceManager.delete(DeleteNamespaceDataClass(namespace_name=NAMESPACE_NAME))
