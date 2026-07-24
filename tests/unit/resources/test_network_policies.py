# builtins
from unittest import TestCase
from unittest.mock import patch, MagicMock

# third party
import yaml

# modules
from src.resources.manifest_loader import render_manifests
from src.resources.namespace_manager import NamespaceManager


EXPECTED = {
    "default-deny-all",
    "allow-dns-egress",
    "allow-ingress-from-socket-ssh",
    "allow-egress-postgres",
    "allow-egress-internet-deny-internal",
}


class TestNetworkPolicyManifest(TestCase):
    '''UNIT: the per-user-namespace NetworkPolicy template renders into the intended isolation set.'''

    def _render(self):
        return render_manifests(
            "user_namespace_netpol.yaml",
            {"NAMESPACE": "u1-namespace", "POD_CIDR": "10.1.0.0/16", "SERVICE_CIDR": "10.96.0.0/12"},
        )

    def test_renders_the_five_policies_scoped_to_namespace(self) -> None:
        docs = self._render()
        self.assertEqual({d["metadata"]["name"] for d in docs}, EXPECTED)
        for d in docs:
            self.assertEqual(d["metadata"]["namespace"], "u1-namespace")

    def test_default_deny_covers_both_directions(self) -> None:
        dd = next(d for d in self._render() if d["metadata"]["name"] == "default-deny-all")
        self.assertEqual(sorted(dd["spec"]["policyTypes"]), ["Egress", "Ingress"])

    def test_internet_rule_excludes_cluster_cidrs(self) -> None:
        pol = next(d for d in self._render() if d["metadata"]["name"] == "allow-egress-internet-deny-internal")
        exc = pol["spec"]["egress"][0]["to"][0]["ipBlock"]["except"]
        self.assertIn("10.1.0.0/16", exc)
        self.assertIn("10.96.0.0/12", exc)

    def test_no_unresolved_placeholders(self) -> None:
        self.assertNotIn("${", yaml.safe_dump_all(self._render()))


class TestApplyNetworkPolicies(TestCase):
    '''UNIT (mocked NetworkingV1Api): NamespaceManager applies every policy to the namespace.'''

    def test_applies_all_policies_to_namespace(self) -> None:
        mock_api = MagicMock()
        with patch("src.resources.namespace_manager.NetworkingV1Api", return_value=mock_api):
            NamespaceManager._apply_network_policies("u1-namespace")
        self.assertEqual(mock_api.create_namespaced_network_policy.call_count, len(EXPECTED))
        for call in mock_api.create_namespaced_network_policy.call_args_list:
            self.assertEqual(call.kwargs["namespace"], "u1-namespace")
            self.assertEqual(call.kwargs["body"]["metadata"]["namespace"], "u1-namespace")
