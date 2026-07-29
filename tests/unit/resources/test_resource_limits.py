# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
import yaml
from kubernetes.client.rest import ApiException

# modules
from src.resources.manifest_loader import render_manifests
from src.resources.namespace_manager import NamespaceManager
from src.resources.resource_config import TIERS, tier_substitutions


class TestResourceQuotaManifest(TestCase):
    '''UNIT: the per-user-namespace ResourceQuota + LimitRange template renders per tier.'''

    def _render(self, tier: str = "free"):
        return render_manifests("user_namespace_quota.yaml", tier_substitutions("u1-namespace", tier))

    def test_renders_quota_and_limitrange_scoped_to_namespace(self) -> None:
        docs = self._render()
        kinds = {d["kind"] for d in docs}
        self.assertEqual(kinds, {"ResourceQuota", "LimitRange"})
        for d in docs:
            self.assertEqual(d["metadata"]["namespace"], "u1-namespace")

    def test_no_unresolved_placeholders(self) -> None:
        self.assertNotIn("${", yaml.safe_dump_all(self._render()))

    def test_quota_carries_tier_numbers(self) -> None:
        quota = next(d for d in self._render("free") if d["kind"] == "ResourceQuota")
        hard = quota["spec"]["hard"]
        self.assertEqual(hard["pods"], TIERS["free"]["MAX_PODS"])
        self.assertEqual(hard["limits.cpu"], TIERS["free"]["TOTAL_CPU_LIMITS"])
        self.assertEqual(hard["requests.storage"], TIERS["free"]["TOTAL_STORAGE"])

    def test_limitrange_has_default_and_max(self) -> None:
        lr = next(d for d in self._render("free") if d["kind"] == "LimitRange")
        item = lr["spec"]["limits"][0]
        self.assertEqual(item["type"], "Container")
        self.assertEqual(item["default"]["cpu"], TIERS["free"]["DEFAULT_CPU"])
        self.assertEqual(item["max"]["memory"], TIERS["free"]["MAX_MEMORY_PER_CONTAINER"])

    def test_pro_tier_is_larger_than_free(self) -> None:
        pro = next(d for d in self._render("pro") if d["kind"] == "ResourceQuota")
        self.assertEqual(pro["spec"]["hard"]["pods"], TIERS["pro"]["MAX_PODS"])
        self.assertNotEqual(TIERS["pro"]["MAX_PODS"], TIERS["free"]["MAX_PODS"])

    def test_unknown_tier_falls_back_to_default(self) -> None:
        subs = tier_substitutions("u1-namespace", "does-not-exist")
        self.assertEqual(subs["MAX_PODS"], TIERS["free"]["MAX_PODS"])


class TestApplyResourceLimits(TestCase):
    '''UNIT (mocked CoreV1Api): create applies both objects; 409 falls back to patch; update patches.'''

    def test_create_applies_quota_and_limitrange(self) -> None:
        mock_api = MagicMock()
        with patch("src.resources.namespace_manager.CoreV1Api", return_value=mock_api):
            NamespaceManager._apply_resource_limits("u1-namespace", "free")
        self.assertEqual(mock_api.create_namespaced_resource_quota.call_count, 1)
        self.assertEqual(mock_api.create_namespaced_limit_range.call_count, 1)
        self.assertEqual(mock_api.patch_namespaced_resource_quota.call_count, 0)

    def test_create_falls_back_to_patch_on_conflict(self) -> None:
        mock_api = MagicMock()
        mock_api.create_namespaced_resource_quota.side_effect = ApiException(status=409)
        mock_api.create_namespaced_limit_range.side_effect = ApiException(status=409)
        with patch("src.resources.namespace_manager.CoreV1Api", return_value=mock_api):
            NamespaceManager._apply_resource_limits("u1-namespace", "free")
        self.assertEqual(mock_api.patch_namespaced_resource_quota.call_count, 1)
        self.assertEqual(mock_api.patch_namespaced_limit_range.call_count, 1)

    def test_update_re_renders_with_new_tier(self) -> None:
        mock_api = MagicMock()
        # simulate objects already exist -> update path should patch with the pro numbers
        mock_api.create_namespaced_resource_quota.side_effect = ApiException(status=409)
        mock_api.create_namespaced_limit_range.side_effect = ApiException(status=409)
        with patch("src.resources.namespace_manager.CoreV1Api", return_value=mock_api):
            NamespaceManager.update_resource_limits("u1-namespace", "pro")
        quota_body = mock_api.patch_namespaced_resource_quota.call_args.kwargs["body"]
        self.assertEqual(quota_body["spec"]["hard"]["pods"], TIERS["pro"]["MAX_PODS"])
