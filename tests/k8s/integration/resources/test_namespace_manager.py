# builtins
from unittest import TestCase


# modules
from src.resources.namespace_manager import NamespaceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass


class TestNamespaceManager(TestCase):        

    def test_namespace_creation_and_removal(self) -> None:
        '''
        Test the creation of namespace
        '''
        print('Test: test_namespace_creation_and_removal')
        # get all namespaces
        dummy_namespace: str = 'test-namespace-manager'
        initial_namespaces: list[dict] = NamespaceManager.list()

        # create the namespace
        namespace: dict = NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': dummy_namespace}))
        namespaces: list[dict] = NamespaceManager.list()

        # assert
        assert namespace.metadata.name == dummy_namespace
        assert len(initial_namespaces) + 1 == len(namespaces)
        assert dummy_namespace in [namespace.metadata.name for namespace in namespaces]

        # remove the namespace
        deleted_namespace: dict = NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': dummy_namespace}))
        assert deleted_namespace['status'] == 'success'

    def test_no_duplicate_namespace_created(self) -> None:
        '''
        Duplicate namespaces should not be created without any errors.
        '''
        print('Test: test_no_duplicate_namespace_created')
        dummy_namespace: str = 'test-namespace-manager'

        # create a namespace
        namespace_first: dict = NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': dummy_namespace}))
        assert namespace_first.metadata.name == dummy_namespace
        namespaces_first: list[dict] = NamespaceManager.list()

        # create the same namespace
        namespace_second: dict = NamespaceManager.create(CreateNamespaceDataClass(**{'namespace_name': dummy_namespace}))
        assert namespace_second.metadata.name == dummy_namespace
        namespaces_second: list[dict] = NamespaceManager.list()
        # assert

        assert len(namespaces_first) == len(namespaces_second)
        assert dummy_namespace in [namespace.metadata.name for namespace in namespaces_first]

        # remove the namespace
        deleted_namespace: dict = NamespaceManager.delete(DeleteNamespaceDataClass(**{'namespace_name': dummy_namespace}))
        assert deleted_namespace['status'] == 'success'
