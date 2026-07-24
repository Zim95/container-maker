"""
Job Manager - Manages Kubernetes Jobs for snapshot building.

This module provides functionality to create and manage Kubernetes Jobs
that handle container snapshot building and pushing.
"""
# built-ins
import os
import time
from typing import Optional

# third-party
from kubernetes.client import BatchV1Api, V1Job, V1JobSpec, V1PodTemplateSpec, V1PodSpec
from kubernetes.client import V1Container, V1EnvVar, V1SecurityContext, V1ObjectMeta
from kubernetes.client import V1VolumeMount, V1Volume, V1PersistentVolumeClaimVolumeSource
from kubernetes.client import RbacAuthorizationV1Api, V1ServiceAccount, V1Role, V1RoleBinding
from kubernetes.client import V1PolicyRule, V1RoleRef, RbacV1Subject
from kubernetes.client import V1PersistentVolumeClaim, V1ResourceRequirements
from kubernetes.client.rest import ApiException

# modules
from src.resources import KubernetesResourceManager
from src.common.logging_setup import get_logger, request_id_var
from src.resources.resource_config import (
    SNAPSHOT_JOB_IMAGE_NAME,
    SNAPSHOT_JOB_TIMEOUT_SECONDS,
    SNAPSHOT_JOB_SERVICE_ACCOUNT,
    SNAPSHOT_JOB_ROLE_NAME,
    SNAPSHOT_JOB_ROLE_BINDING_NAME,
    SNAPSHOT_DIR,
    SNAPSHOT_PVC_NAME,
    SNAPSHOT_PVC_SIZE
)

logger = get_logger("job_manager")


class JobManager(KubernetesResourceManager):
    """Manages Kubernetes Jobs for snapshot operations."""
    
    @classmethod
    def _ensure_snapshot_job_rbac(cls, namespace_name: str) -> None:
        """
        Ensure RBAC resources exist for snapshot jobs.
        Creates ServiceAccount, Role, and RoleBinding if they don't exist.
        
        :param namespace_name: Namespace to create RBAC resources in
        """
        rbac_api = RbacAuthorizationV1Api()
        
        # Create ServiceAccount if it doesn't exist
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
        
        # Create Role if it doesn't exist (needs access to pods for volume mounting)
        try:
            rbac_api.read_namespaced_role(
                name=SNAPSHOT_JOB_ROLE_NAME,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                role = V1Role(
                    metadata=V1ObjectMeta(
                        name=SNAPSHOT_JOB_ROLE_NAME,
                        namespace=namespace_name
                    ),
                    rules=[
                        V1PolicyRule(
                            api_groups=[''],
                            resources=['pods', 'pods/log'],
                            verbs=['get', 'list']
                        )
                    ]
                )
                rbac_api.create_namespaced_role(namespace_name, role)
                logger.info("created snapshot job Role", extra={"role_name": SNAPSHOT_JOB_ROLE_NAME, "namespace_name": namespace_name})
            else:
                raise
        
        # Create RoleBinding if it doesn't exist
        try:
            rbac_api.read_namespaced_role_binding(
                name=SNAPSHOT_JOB_ROLE_BINDING_NAME,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                role_binding = V1RoleBinding(
                    metadata=V1ObjectMeta(
                        name=SNAPSHOT_JOB_ROLE_BINDING_NAME,
                        namespace=namespace_name
                    ),
                    subjects=[
                        RbacV1Subject(
                            kind='ServiceAccount',
                            name=SNAPSHOT_JOB_SERVICE_ACCOUNT,
                            namespace=namespace_name
                        )
                    ],
                    role_ref=V1RoleRef(
                        api_group='rbac.authorization.k8s.io',
                        kind='Role',
                        name=SNAPSHOT_JOB_ROLE_NAME
                    )
                )
                rbac_api.create_namespaced_role_binding(namespace_name, role_binding)
                logger.info("created snapshot job RoleBinding", extra={"role_binding_name": SNAPSHOT_JOB_ROLE_BINDING_NAME, "namespace_name": namespace_name})
            else:
                raise

    @classmethod
    def _ensure_snapshot_pvc(cls, namespace_name: str) -> None:
        """
        Ensure PersistentVolumeClaim exists for snapshot storage in the given namespace.
        Creates PVC if it doesn't exist.
        This is idempotent - safe to call multiple times.

        :param namespace_name: Namespace to create PVC in
        """
        try:
            cls.client.read_namespaced_persistent_volume_claim(
                name=SNAPSHOT_PVC_NAME,
                namespace=namespace_name
            )
        except ApiException as e:
            if e.status == 404:
                pvc = V1PersistentVolumeClaim(
                    metadata=V1ObjectMeta(
                        name=SNAPSHOT_PVC_NAME,
                        namespace=namespace_name
                    ),
                    spec={
                        'accessModes': ['ReadWriteMany'],
                        'resources': {
                            'requests': {
                                'storage': SNAPSHOT_PVC_SIZE
                            }
                        }
                    }
                )
                cls.client.create_namespaced_persistent_volume_claim(namespace_name, pvc)
                logger.info("created snapshot PersistentVolumeClaim", extra={"pvc_name": SNAPSHOT_PVC_NAME, "namespace_name": namespace_name})
            else:
                raise

    @classmethod
    def create_snapshot_job(
        cls,
        namespace_name: str,
        pod_name: str,
        container_id: str,
        repo_name: str,
        repo_password: str,
        db_host: str,
        db_port: int,
        db_username: str,
        db_password: str,
        db_database: str,
        snapshot_path: str,
        storage_env_vars: dict
    ) -> dict:
        """
        Create a Kubernetes Job to build and push a container snapshot.
        
        :param namespace_name: Namespace to create the job in
        :param pod_name: Name of the pod being snapshotted
        :param container_id: Database ID of the container
        :param repo_name: Docker registry repository name
        :param repo_password: Docker registry password
        :param db_host: Database host
        :param db_port: Database port
        :param db_username: Database username
        :param db_password: Database password
        :param db_database: Database name
        :param snapshot_path: Path to the snapshot (local path or MinIO key)
        :param storage_env_vars: Storage layer specific env vars
        :return: dict with job_name
        """
        try:
            cls.check_kubernetes_client()
            
            # Ensure RBAC resources exist
            cls._ensure_snapshot_job_rbac(namespace_name)
            
            # Ensure PVC exists for local storage
            cls._ensure_snapshot_pvc(namespace_name)
            
            job_name = f"{pod_name}-snapshot-job"
            
            # storage-specific env vars (STORAGE_LAYER, MINIO_*, SNAPSHOT_DIR) -> list of V1EnvVar
            storage_env_list = [V1EnvVar(name=key, value=str(value)) for key, value in storage_env_vars.items() if value is not None]

            # Job container with privileged access (needs a Docker daemon to build/push)
            job_env = {
                "CONTAINER_ID": container_id,
                "POD_NAME": pod_name,
                "NAMESPACE_NAME": namespace_name,
                "REPO_NAME": repo_name,
                "REPO_PASSWORD": repo_password,
                "DB_HOST": db_host,
                "DB_PORT": str(db_port),
                "DB_USERNAME": db_username,
                "DB_PASSWORD": db_password,
                "DB_DATABASE": db_database,
                "SNAPSHOT_PATH": snapshot_path,
                "SNAPSHOT_DIR": SNAPSHOT_DIR,
                # Propagate the caller's correlation id into the detached Job so its logs
                # (a separate process/pod) can be tied back to the originating request.
                "REQUEST_ID": request_id_var.get(),
            }

            job_env_vars = [V1EnvVar(name=key, value=str(value)) for key, value in job_env.items() if value is not None]
            # Merge the storage env vars in as individual vars (not a stringified list).
            job_env_vars.extend(storage_env_list)

            storage_layer = os.getenv("STORAGE_LAYER", "local").lower()

            job_container = V1Container(
                name="snapshot-builder",
                image=SNAPSHOT_JOB_IMAGE_NAME,
                security_context=V1SecurityContext(
                    privileged=True  # Required for Docker daemon
                ),
                env=job_env_vars,
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
                        volumes=[
                            V1Volume(
                                name="snapshot-volume",
                                empty_dir={} if storage_layer == "minio" else None,
                                persistent_volume_claim=None if storage_layer == "minio" else V1PersistentVolumeClaimVolumeSource(
                                    claim_name=SNAPSHOT_PVC_NAME
                                )
                            )
                        ],
                        restart_policy="Never",  # Don't restart on failure
                        service_account_name=SNAPSHOT_JOB_SERVICE_ACCOUNT
                    )
                ),
                backoff_limit=2,  # Retry up to 2 times
                ttl_seconds_after_finished=3600  # Auto-cleanup after 1 hour
            )
            
            job = V1Job(
                metadata=V1ObjectMeta(name=job_name, namespace=namespace_name),
                spec=job_spec
            )
            
            # Create the job
            batch_v1 = BatchV1Api()
            batch_v1.create_namespaced_job(namespace=namespace_name, body=job)
            
            logger.info("created snapshot job", extra={"job_name": job_name, "namespace_name": namespace_name, "pod_name": pod_name, "container_id": container_id})

            return {"job_name": job_name, "namespace_name": namespace_name}
            
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
