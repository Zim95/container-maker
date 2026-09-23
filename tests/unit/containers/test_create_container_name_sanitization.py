# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# modules
from src.containers.containers import KubernetesContainerHelper, KubernetesContainerManager
from src.containers.dataclasses.create_container_dataclass import CreateContainerDataClass, ExposureLevel


class TestSanitizeName(TestCase):
    '''Unit tests for _sanitize_name - the Kubernetes-DNS-label normalization every k8s-facing
    identifier in create() now goes through.'''

    def test_lowercases_and_replaces_spaces_and_underscores_with_hyphens(self) -> None:
        self.assertEqual(KubernetesContainerHelper._sanitize_name('Namah_SSH_Ubuntu Test'), 'namah-ssh-ubuntu-test')

    def test_drops_characters_outside_lowercase_alphanumeric_and_hyphen(self) -> None:
        self.assertEqual(KubernetesContainerHelper._sanitize_name('my.container!@#'), 'mycontainer')

    def test_strips_leading_and_trailing_hyphens(self) -> None:
        '''RFC 1123: a k8s name must start and end with an alphanumeric character.'''
        self.assertEqual(KubernetesContainerHelper._sanitize_name('_leading_and_trailing_'), 'leading-and-trailing')

    def test_empty_or_all_invalid_input_falls_back_to_a_safe_default(self) -> None:
        self.assertEqual(KubernetesContainerHelper._sanitize_name(''), 'container')
        self.assertEqual(KubernetesContainerHelper._sanitize_name('___'), 'container')


class TestCreateSanitizesNameBeforeBuildingK8sIdentifiers(TestCase):
    '''
    Regression test for a real production bug: create() built pod_name/container_name straight
    from data.container_name with no sanitization, so a user-chosen name like
    "namah_ssh_ubuntu_test" (underscores are a normal, allowed character in Cloud's own free-form
    container name) reached Kubernetes verbatim and every create attempt failed with "a lowercase
    RFC 1123 subdomain must consist of...". _sanitize_name already existed (used by
    find_container_pod's fallback label match) but nothing called it at creation time - this
    tests that create() now does.
    '''

    def setUp(self) -> None:
        self.data = CreateContainerDataClass(
            image_name='browseterm/base:latest',
            container_name='namah_ssh_ubuntu_test',
            network_name='ns-1',
            exposure_level=ExposureLevel.INTERNAL,
            publish_information=[],
            environment_variables={},
        )

    def test_pod_and_container_name_are_sanitized(self) -> None:
        with patch('src.containers.containers.NamespaceManager.create', return_value=None), \
             patch('src.containers.containers.PodManager.create') as mock_pod_create:
            mock_pod_create.return_value = {
                'resource_type': 'pod', 'pod_id': 'uid-1', 'pod_name': 'namah-ssh-ubuntu-test-pod-123',
                'pod_ip': '10.0.0.1', 'pod_namespace': 'ns-1', 'pod_ports': [], 'associated_resources': [],
            }
            KubernetesContainerManager.create(self.data)

            create_pod_data = mock_pod_create.call_args.args[0]
            self.assertEqual(create_pod_data.container_name, 'namah-ssh-ubuntu-test')
            self.assertTrue(create_pod_data.pod_name.startswith('namah-ssh-ubuntu-test-pod-'))
            self.assertNotIn('_', create_pod_data.pod_name)
            self.assertNotIn('_', create_pod_data.container_name)
