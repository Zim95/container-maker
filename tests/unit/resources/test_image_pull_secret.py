# builtins
import base64
import json
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
from kubernetes.client.rest import ApiException

# modules
from src.resources.namespace_manager import NamespaceManager
from src.resources.resource_config import USER_POD_IMAGE_PULL_SECRET_NAME


class TestApplyImagePullSecret(TestCase):
    '''
    UNIT (mocked CoreV1Api): a saved/resumed snapshot image lives in a PRIVATE Docker Hub
    repository under the same account snapshot_job already pushes to - a real, reproduced
    ImagePullBackOff ("insufficient_scope: authorization failed") happened live because no pull
    secret had ever been created in the user's namespace. Regression coverage for the fix.
    '''

    def test_creates_a_dockerconfigjson_secret_with_the_real_credentials(self) -> None:
        mock_api = MagicMock()
        with patch("src.resources.namespace_manager.CoreV1Api", return_value=mock_api), \
             patch("src.resources.namespace_manager.REPO_NAME", "zim95"), \
             patch("src.resources.namespace_manager.REPO_PASSWORD", "hunter2"):
            NamespaceManager._apply_image_pull_secret("u1-namespace")

        mock_api.create_namespaced_secret.assert_called_once()
        kwargs = mock_api.create_namespaced_secret.call_args.kwargs
        self.assertEqual(kwargs["namespace"], "u1-namespace")
        secret = kwargs["body"]
        self.assertEqual(secret.metadata.name, USER_POD_IMAGE_PULL_SECRET_NAME)
        self.assertEqual(secret.type, "kubernetes.io/dockerconfigjson")
        decoded = json.loads(base64.b64decode(secret.data[".dockerconfigjson"]))
        auth_entry = decoded["auths"]["https://index.docker.io/v1/"]
        self.assertEqual(auth_entry["username"], "zim95")
        self.assertEqual(auth_entry["password"], "hunter2")
        self.assertEqual(
            base64.b64decode(auth_entry["auth"]).decode(), "zim95:hunter2",
        )

    def test_falls_back_to_patch_on_conflict(self) -> None:
        mock_api = MagicMock()
        mock_api.create_namespaced_secret.side_effect = ApiException(status=409)
        with patch("src.resources.namespace_manager.CoreV1Api", return_value=mock_api), \
             patch("src.resources.namespace_manager.REPO_NAME", "zim95"), \
             patch("src.resources.namespace_manager.REPO_PASSWORD", "hunter2"):
            NamespaceManager._apply_image_pull_secret("u1-namespace")

        mock_api.patch_namespaced_secret.assert_called_once()
        self.assertEqual(mock_api.patch_namespaced_secret.call_args.kwargs["name"], USER_POD_IMAGE_PULL_SECRET_NAME)

    def test_does_nothing_and_logs_when_credentials_are_not_configured(self) -> None:
        mock_api = MagicMock()
        with patch("src.resources.namespace_manager.CoreV1Api", return_value=mock_api), \
             patch("src.resources.namespace_manager.REPO_NAME", None), \
             patch("src.resources.namespace_manager.REPO_PASSWORD", None):
            NamespaceManager._apply_image_pull_secret("u1-namespace")

        mock_api.create_namespaced_secret.assert_not_called()

    def test_create_applies_pull_secret_for_a_brand_new_namespace(self) -> None:
        mock_get_client = MagicMock()
        with patch.object(NamespaceManager, "get", return_value={}), \
             patch.object(NamespaceManager, "check_kubernetes_client", return_value=None), \
             patch.object(NamespaceManager, "client", mock_get_client), \
             patch.object(NamespaceManager, "_apply_network_policies") as mock_netpol, \
             patch.object(NamespaceManager, "_apply_resource_limits") as mock_quota, \
             patch.object(NamespaceManager, "_apply_image_pull_secret") as mock_pull_secret:
            from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
            NamespaceManager.create(CreateNamespaceDataClass(namespace_name="u1-namespace"))

        mock_pull_secret.assert_called_once_with("u1-namespace")
        mock_netpol.assert_called_once()
        mock_quota.assert_called_once()

    def test_create_still_applies_pull_secret_for_an_already_existing_namespace(self) -> None:
        '''
        The exact gap that let this bug ship silently: every existing user's namespace was
        already created before this fix existed, and create() short-circuits on an existing
        namespace - so the pull secret must be applied on THAT path too, not only the
        brand-new-namespace path, or no existing user would ever get it.
        '''
        with patch.object(NamespaceManager, "get", return_value={"namespace_name": "u1-namespace"}), \
             patch.object(NamespaceManager, "_apply_image_pull_secret") as mock_pull_secret, \
             patch.object(NamespaceManager, "_apply_network_policies") as mock_netpol, \
             patch.object(NamespaceManager, "_apply_resource_limits") as mock_quota:
            from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
            NamespaceManager.create(CreateNamespaceDataClass(namespace_name="u1-namespace"))

        mock_pull_secret.assert_called_once_with("u1-namespace")
        # The already-exists path must NOT re-apply the create-time-only steps.
        mock_netpol.assert_not_called()
        mock_quota.assert_not_called()
