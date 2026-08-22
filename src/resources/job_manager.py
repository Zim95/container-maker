"""
Job Manager - Manages Kubernetes Jobs for snapshot building.

This module provides functionality to create and manage Kubernetes Jobs
that handle container snapshot building and pushing.
"""
# built-ins
import time
import uuid
from typing import Optional

# third-party
from kubernetes.client import BatchV1Api, V1Job, V1JobSpec, V1PodTemplateSpec, V1PodSpec
from kubernetes.client import V1Container, V1EnvVar, V1SecurityContext, V1ObjectMeta
from kubernetes.client import V1EnvFromSource, V1SecretEnvSource
from kubernetes.client import V1VolumeMount, V1Volume
from kubernetes.client import V1ServiceAccount
from kubernetes.client import V1ResourceRequirements
from kubernetes.client.rest import ApiException

# modules
from src.resources import KubernetesResourceManager
from src.common.logging_setup import get_logger, request_id_var
from src.resources.resource_config import (
    SNAPSHOT_JOB_IMAGE_NAME,
    SNAPSHOT_JOB_TIMEOUT_SECONDS,
    SNAPSHOT_JOB_SERVICE_ACCOUNT,
    SNAPSHOT_DIR,
)

logger = get_logger("job_manager")

# The snapshot Job reads DB credentials from this Secret (created at cluster setup in the trusted
# namespace) via envFrom, instead of receiving them as literal env values.
DB_CREDENTIALS_SECRET_NAME: str = 'browseterm-db-credentials'


class JobManager(KubernetesResourceManager):
    """Manages Kubernetes Jobs for snapshot operations."""
    
    @classmethod
    def _ensure_snapshot_job_sa(cls, namespace_name: str) -> None:
        """
        Ensure the snapshot Job's ServiceAccount exists in the given namespace.

        The Job talks only to MinIO / the registry / Postgres over the network — never the k8s API —
        so it needs NO Role/RoleBinding. We keep a dedicated, permission-less ServiceAccount and mount
        no token for it (see automount_service_account_token=False on the Job pod).

        :param namespace_name: Namespace to create the ServiceAccount in
        """
        try:
            cls.client.read_namespaced_service_account(
                name=SNAPSHOT_JOB_SERVICE_ACCOUNT,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                service_account = V1ServiceAccount(
                    metadata=V1ObjectMeta(
                        name=SNAPSHOT_JOB_SERVICE_ACCOUNT,
                        namespace=namespace_name
                    )
                )
                cls.client.create_namespaced_service_account(namespace_name, service_account)
                logger.info("created snapshot job ServiceAccount", extra={"service_account": SNAPSHOT_JOB_SERVICE_ACCOUNT, "namespace_name": namespace_name})
            else:
                raise

    @classmethod
    def create_snapshot_job(
        cls,
        job_namespace: str,
        user_namespace: str,
        pod_name: str,
        container_id: str,
        repo_name: str,
        repo_password: str,
        snapshot_path: str,
        storage_env_vars: dict
    ) -> dict:
        """
        Create a Kubernetes Job to build and push a container snapshot.

        The Job runs in the TRUSTED namespace (job_namespace, e.g. `browseterm`), NOT the user's
        namespace: it only talks to MinIO / the registry / Postgres over the network, never the user
        pod, so it has no reason to sit inside the tenant's namespace. It reads DB credentials from
        the `browseterm-db-credentials` Secret (which lives in the trusted namespace) via envFrom —
        no DB password is passed as a literal env value. user_namespace is still threaded through as
        the NAMESPACE_NAME env so the Job can locate this container's tar in MinIO.

        :param job_namespace: Trusted namespace to CREATE THE JOB in (has the DB Secret)
        :param user_namespace: The user pod's namespace (used only to locate the MinIO snapshot key)
        :param pod_name: Name of the pod being snapshotted
        :param container_id: Database ID of the container
        :param repo_name: Docker registry repository name
        :param repo_password: Docker registry password
        :param snapshot_path: MinIO object key of the snapshot tar
        :param storage_env_vars: Storage layer specific env vars
        :return: dict with job_name + namespace_name (the trusted namespace the Job runs in)
        """
        try:
            cls.check_kubernetes_client()

            # Ensure the Job's (permission-less) ServiceAccount exists in the trusted namespace
            cls._ensure_snapshot_job_sa(job_namespace)

            # Unique per attempt: the Job controller auto-labels its Pods with job-name=<this>,
            # and label values are capped at 63 chars, so keep the suffix short rather than a
            # full timestamp. A deterministic name here would collide with a still-TTL'd Job
            # from a prior save of the same pod (ttl_seconds_after_finished below is 1h).
            job_name = f"{pod_name}-snapshot-job-{uuid.uuid4().hex[:8]}"
            
            # storage-specific env vars (STORAGE_LAYER, MINIO_*, SNAPSHOT_DIR) -> list of V1EnvVar
            storage_env_list = [V1EnvVar(name=key, value=str(value)) for key, value in storage_env_vars.items() if value is not None]

            # Job container with privileged access (needs a Docker daemon to build/push).
            # DB_* are NOT here — they come from the browseterm-db-credentials Secret via envFrom
            # (below). NAMESPACE_NAME is the USER namespace so the Job can find this container's tar
            # in MinIO, even though the Job itself runs in the trusted namespace.
            job_env = {
                "CONTAINER_ID": container_id,
                "POD_NAME": pod_name,
                "NAMESPACE_NAME": user_namespace,
                "REPO_NAME": repo_name,
                "REPO_PASSWORD": repo_password,
                "SNAPSHOT_PATH": snapshot_path,
                "SNAPSHOT_DIR": SNAPSHOT_DIR,
                # Propagate the caller's correlation id into the detached Job so its logs
                # (a separate process/pod) can be tied back to the originating request.
                "REQUEST_ID": request_id_var.get(),
            }

            job_env_vars = [V1EnvVar(name=key, value=str(value)) for key, value in job_env.items() if value is not None]
            # Merge the storage env vars in as individual vars (not a stringified list).
            job_env_vars.extend(storage_env_list)

            job_container = V1Container(
                name="snapshot-builder",
                image=SNAPSHOT_JOB_IMAGE_NAME,
                security_context=V1SecurityContext(
                    privileged=True  # Required for Docker daemon
                ),
                env=job_env_vars,
                # DB_HOST/PORT/USERNAME/PASSWORD/DATABASE from the Secret in the trusted namespace.
                env_from=[V1EnvFromSource(secret_ref=V1SecretEnvSource(name=DB_CREDENTIALS_SECRET_NAME))],
                volume_mounts=[
                    V1VolumeMount(
                        name="snapshot-volume",
                        mount_path=SNAPSHOT_DIR
                    )
                ]
            )
            
            # Job spec - runs once and terminates
            job_spec = V1JobSpec(
                template=V1PodTemplateSpec(
                    spec=V1PodSpec(
                        containers=[job_container],
                        # emptyDir scratch for unpacking the tar pulled from MinIO. Local PVC storage
                        # is retired — snapshots always live in object storage now.
                        volumes=[
                            V1Volume(name="snapshot-volume", empty_dir={})
                        ],
                        restart_policy="Never",  # Don't restart on failure
                        service_account_name=SNAPSHOT_JOB_SERVICE_ACCOUNT,
                        # The Job never calls the k8s API, so don't mount its SA token.
                        automount_service_account_token=False
                    )
                ),
                backoff_limit=2,  # Retry up to 2 times
                ttl_seconds_after_finished=3600  # Auto-cleanup after 1 hour
            )
            
            job = V1Job(
                metadata=V1ObjectMeta(name=job_name, namespace=job_namespace),
                spec=job_spec
            )

            # Create the job in the trusted namespace
            batch_v1 = BatchV1Api()
            batch_v1.create_namespaced_job(namespace=job_namespace, body=job)

            logger.info("created snapshot job", extra={"job_name": job_name, "namespace_name": job_namespace, "user_namespace": user_namespace, "pod_name": pod_name, "container_id": container_id})

            return {"job_name": job_name, "namespace_name": job_namespace}
            
        except ApiException as ae:
            raise ApiException(f'Error creating snapshot job: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Error creating snapshot job: {str(e)}') from e
    
    @classmethod
    def wait_for_job_completion(
        cls,
        namespace_name: str,
        job_name: str,
        timeout_seconds: float = SNAPSHOT_JOB_TIMEOUT_SECONDS
    ) -> dict:
        """
        Wait for a job to complete.
        
        :param namespace_name: Namespace of the job
        :param job_name: Name of the job
        :param timeout_seconds: Timeout in seconds
        :return: dict with status
        """
        try:
            cls.check_kubernetes_client()
            batch_v1 = BatchV1Api()
            
            start_time = time.time()
            
            while time.time() - start_time < timeout_seconds:
                job = batch_v1.read_namespaced_job_status(
                    name=job_name,
                    namespace=namespace_name
                )
                
                # Check if job succeeded
                if job.status.succeeded and job.status.succeeded > 0:
                    logger.info("snapshot job completed successfully", extra={"job_name": job_name, "namespace_name": namespace_name})
                    return {"status": "succeeded", "job_name": job_name}

                # Check if job failed
                if job.status.failed and job.status.failed > 0:
                    error_msg = f"Job {job_name} failed"
                    logger.error(error_msg, extra={"job_name": job_name, "namespace_name": namespace_name})
                    raise Exception(error_msg)
                
                # Still running, wait a bit
                time.sleep(5)
            
            # Timeout reached
            raise TimeoutError(
                f"Job {job_name} did not complete within {timeout_seconds} seconds"
            )
            
        except ApiException as ae:
            raise ApiException(f'Error waiting for job: {str(ae)}') from ae
        except TimeoutError as te:
            raise te
        except Exception as e:
            raise Exception(f'Error waiting for job: {str(e)}') from e
    
    @classmethod
    def delete_job(cls, namespace_name: str, job_name: str) -> dict:
        """
        Delete a job.
        
        :param namespace_name: Namespace of the job
        :param job_name: Name of the job
        :return: dict with status
        """
        try:
            cls.check_kubernetes_client()
            batch_v1 = BatchV1Api()
            
            batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=namespace_name,
                propagation_policy='Foreground'  # Delete pods too
            )
            
            logger.info("deleted job", extra={"job_name": job_name, "namespace_name": namespace_name})
            return {"status": "deleted", "job_name": job_name}
            
        except ApiException as e:
            if e.status == 404:
                return {"status": "not_found", "job_name": job_name}
            raise ApiException(f'Error deleting job: {str(e)}') from e
        except Exception as e:
            raise Exception(f'Error deleting job: {str(e)}') from e
