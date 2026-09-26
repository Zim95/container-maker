# modules
import base64
import json
import time
from src.resources.dataclasses.namespace.get_namespace_dataclass import GetNamespaceDataClass
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.namespace.create_namespace_dataclass import CreateNamespaceDataClass
from src.resources.dataclasses.namespace.delete_namespace_dataclass import DeleteNamespaceDataClass
from src.common.config import REPO_NAME, REPO_PASSWORD
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.common.logging_setup import get_logger
from src.resources.manifest_loader import render_manifests
from src.resources.resource_config import POD_CIDR, SERVICE_CIDR, tier_substitutions, USER_POD_IMAGE_PULL_SECRET_NAME

# third party
from kubernetes.client import V1Namespace
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1Secret
from kubernetes.client import NetworkingV1Api
from kubernetes.client import CoreV1Api
from kubernetes.client.rest import ApiException

logger = get_logger("namespace_manager")


class NamespaceManager(KubernetesResourceManager):
    '''
    Manage kubernetes namespaces.
    '''
    @classmethod
    def list(cls) -> list[dict]:
        '''
        List all available namespaces.
        :params: None
        :returns: list[dict]: List of namespaces
        '''
        try:
            cls.check_kubernetes_client()
            return [
                {
                    'namespace_id': ns.metadata.uid,
                    'namespace_name': ns.metadata.name,
                }
                for ns in cls.client.list_namespace().items
            ]
        except ApiException as ae:
            raise ApiException(f'Error occured while listing namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def get(cls, data: GetNamespaceDataClass) -> dict:
        '''
        Get a namespace.
        :params: data: GetNamespaceDataClass
        :returns: dict: Namespace Details
        '''
        try:
            cls.check_kubernetes_client()
            response: V1Namespace = cls.client.read_namespace(name=data.namespace_name)
            return {
                'namespace_id': response.metadata.uid,
                'namespace_name': response.metadata.name,
            }
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occured while getting namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def create(cls, data: CreateNamespaceDataClass) -> dict:
        '''
        Create a namespace. Return if already exists.
        :params: data: CreateNamespaceDataClass
        :returns: dict: Namespace Details
        '''
        try:
            ns: dict = cls.get(GetNamespaceDataClass(namespace_name=data.namespace_name))
            if ns:
                # The namespace already exists (every user's namespace, after their very first
                # container) - _apply_image_pull_secret still needs to run here, not just on the
                # brand-new-namespace path below. It shipped after every current user's namespace
                # was already created, and this create() call is what runs on every single
                # Create/Resume (containers.py's own create()) - without this, an existing user's
                # namespace would never pick up the secret at all, since nothing else ever
                # revisits an already-created namespace. Idempotent either way.
                cls._apply_image_pull_secret(data.namespace_name)
                return ns
            namespace: V1Namespace = V1Namespace(
                metadata=V1ObjectMeta(name=data.namespace_name)
            )
            created: V1Namespace = cls.client.create_namespace(namespace)
            # Apply the isolation NetworkPolicies for this per-user namespace.
            cls._apply_network_policies(data.namespace_name)
            # Apply the ResourceQuota + LimitRange for the user's tier (noisy-neighbor / DoS bound).
            cls._apply_resource_limits(data.namespace_name, data.tier)
            # Real registry pull credentials for a saved/resumed snapshot image - see
            # USER_POD_IMAGE_PULL_SECRET_NAME's own docstring for the incident this closes.
            cls._apply_image_pull_secret(data.namespace_name)
            return {
                'namespace_id': created.metadata.uid,
                'namespace_name': created.metadata.name
            }
        except ApiException as ae:
            raise ApiException(f'Error occured while creating namespace: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def _apply_network_policies(cls, namespace_name: str) -> None:
        '''
        Apply the per-user-namespace isolation NetworkPolicies from the manifest template
        (src/resources/manifests/user_namespace_netpol.yaml): default-deny + narrow allows for DNS,
        socket-ssh ingress on :22, Postgres egress, and internet egress (minus the cluster CIDRs).
        Idempotent (409 = already exists is ignored).
        NOTE: only ENFORCED by a policy-capable CNI (Calico/Cilium); docker-desktop accepts but
        does not enforce them.
        '''
        docs: list[dict] = render_manifests(
            "user_namespace_netpol.yaml",
            {"NAMESPACE": namespace_name, "POD_CIDR": POD_CIDR, "SERVICE_CIDR": SERVICE_CIDR},
        )
        networking_api: NetworkingV1Api = NetworkingV1Api()
        for doc in docs:
            try:
                networking_api.create_namespaced_network_policy(namespace=namespace_name, body=doc)
            except ApiException as ae:
                if ae.status == 409:  # already exists — idempotent re-apply
                    continue
                raise
        logger.info("applied network policies", extra={"namespace_name": namespace_name, "count": len(docs)})

    @classmethod
    def _apply_resource_limits(cls, namespace_name: str, tier: str) -> None:
        '''
        Apply the tier's ResourceQuota + LimitRange (src/resources/manifests/user_namespace_quota.yaml)
        to a per-user namespace at creation time. Idempotent: on 409 (already exists) it PATCHes the
        existing object instead, so calling create again with a different tier re-syncs the limits.
        '''
        cls._render_and_apply_resource_limits(namespace_name, tier)

    @classmethod
    def update_resource_limits(cls, namespace_name: str, tier: str) -> None:
        '''
        Change a user's resources when their plan/tier changes: re-render the quota template with the
        new tier's numbers and PATCH the live ResourceQuota + LimitRange. This is the "resize" path —
        raising limits takes effect immediately; lowering them applies to the next pod (re)created
        (k8s does not evict running pods that exceed a newly-lowered quota).
        '''
        cls._render_and_apply_resource_limits(namespace_name, tier)
        logger.info("updated resource limits", extra={"namespace_name": namespace_name, "tier": tier})

    @classmethod
    def _render_and_apply_resource_limits(cls, namespace_name: str, tier: str) -> None:
        '''
        Render user_namespace_quota.yaml for (namespace, tier) and create-or-patch each document.
        Shared by _apply_resource_limits (create) and update_resource_limits (plan change).
        '''
        docs: list[dict] = render_manifests(
            "user_namespace_quota.yaml",
            tier_substitutions(namespace_name, tier),
        )
        core_api: CoreV1Api = CoreV1Api()
        creators = {
            "ResourceQuota": (core_api.create_namespaced_resource_quota, core_api.patch_namespaced_resource_quota),
            "LimitRange": (core_api.create_namespaced_limit_range, core_api.patch_namespaced_limit_range),
        }
        for doc in docs:
            kind: str = doc["kind"]
            name: str = doc["metadata"]["name"]
            create_fn, patch_fn = creators[kind]
            try:
                create_fn(namespace=namespace_name, body=doc)
            except ApiException as ae:
                if ae.status == 409:  # already exists -> patch it to the (possibly new) tier values
                    patch_fn(name=name, namespace=namespace_name, body=doc)
                    continue
                raise
        logger.info("applied resource limits", extra={"namespace_name": namespace_name, "tier": tier, "count": len(docs)})

    @classmethod
    def _apply_image_pull_secret(cls, namespace_name: str) -> None:
        '''
        Create (or refresh) the Docker Hub pull-credential Secret every user pod's spec
        references (see USER_POD_IMAGE_PULL_SECRET_NAME's own docstring for the real incident
        this fixes: a saved/resumed snapshot image is private, and pulling it failed with
        "insufficient_scope: authorization failed" because nothing had ever created a pull
        secret in the user's own namespace before). Uses the exact same REPO_NAME/REPO_PASSWORD
        credential snapshot_job already authenticates with to push these images in the first
        place - same account, both directions. Idempotent (create-or-patch), same pattern as
        _apply_resource_limits.
        '''
        if not REPO_NAME or not REPO_PASSWORD:
            logger.error(
                "cannot create image pull secret: REPO_NAME/REPO_PASSWORD not configured",
                extra={"namespace_name": namespace_name},
            )
            return
        auth_b64 = base64.b64encode(f"{REPO_NAME}:{REPO_PASSWORD}".encode()).decode()
        dockerconfigjson = json.dumps({
            "auths": {"https://index.docker.io/v1/": {
                "username": REPO_NAME, "password": REPO_PASSWORD, "auth": auth_b64,
            }},
        }).encode()
        secret = V1Secret(
            metadata=V1ObjectMeta(name=USER_POD_IMAGE_PULL_SECRET_NAME),
            type="kubernetes.io/dockerconfigjson",
            data={".dockerconfigjson": base64.b64encode(dockerconfigjson).decode()},
        )
        core_api: CoreV1Api = CoreV1Api()
        try:
            core_api.create_namespaced_secret(namespace=namespace_name, body=secret)
        except ApiException as ae:
            if ae.status == 409:  # already exists - refresh in case the credential rotated
                core_api.patch_namespaced_secret(
                    name=USER_POD_IMAGE_PULL_SECRET_NAME, namespace=namespace_name, body=secret,
                )
            else:
                raise
        logger.info("applied image pull secret", extra={"namespace_name": namespace_name})

    @classmethod
    def poll_termination(cls, namespace_name: str, timeout_seconds: float = 2.0) -> None:
        '''
        Poll the termination of a namespace.
        '''
        is_terminated: bool = False
        while is_terminated != True:
            ns: dict = cls.get(GetNamespaceDataClass(namespace_name=namespace_name))
            is_terminated = (ns == {})
            logger.info("polling namespace termination", extra={"namespace_name": namespace_name, "is_terminated": is_terminated})
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeleteNamespaceDataClass) -> dict:
        '''
        Delete a namespace.
        :params: namespace_name: str
        :returns: dict: Deletion status
        '''
        try:
            cls.check_kubernetes_client()
            # Call Kubernetes API to delete the namespace
            deletion_response = cls.client.delete_namespace(data.namespace_name)
            cls.poll_termination(data.namespace_name)
            return {"status": "success", "message": f"Namespace '{data.namespace_name}' deleted.", "details": deletion_response.to_dict()}
        except ApiException as ae:
            raise ApiException(f"Error occurred while deleting namespace '{data.namespace_name}': {str(ae)}") from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f"Unsupported Runtime Environment: {str(ure)}") from ure
        except Exception as e:
            raise Exception(f"Unknown error occurred: {str(e)}") from e
