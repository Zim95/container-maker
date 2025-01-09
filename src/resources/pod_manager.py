# modules
import time
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.resource_manager import KubernetesResourceManager
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.common.exceptions import UnsupportedRuntimeEnvironment

# third party
from kubernetes.client.rest import ApiException
from kubernetes.client import V1EnvVar
from kubernetes.client import V1ContainerPort
from kubernetes.client import V1Pod
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1PodSpec
from kubernetes.client import V1Container


class PodManager(KubernetesResourceManager):
    '''
    Manage kubernetes pods.
    '''

    @classmethod
    def list(cls, data: ListPodDataClass) -> list[dict]:
        try:
            cls.check_kubernetes_client()
            return cls.client.list_namespaced_pod(namespace=data.namespace_name).items
        except ApiException as ae:
            raise ApiException(f'Error occured while listing pods: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def create(cls, data: CreatePodDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            pods: list[dict] = cls.list(ListPodDataClass(**{'namespace_name': data.namespace_name}))
            pod_name_id_map: dict = {
                pod.metadata.name: {'pod_id': pod.metadata.uid, 'pod_namespace': pod.metadata.namespace} for pod in pods}
            
            # highly unlikely: If pod name already exists. Then return it. Dont create a new one.
            if data.pod_name in pod_name_id_map.keys():
                return pod_name_id_map[data.pod_name]

            # create environment variable list
            environment_variables: list[V1EnvVar] = [
                V1EnvVar(name=name, value=value)
                for name, value in data.environment_variables.items()
            ]

            # create target port list
            target_ports: list[V1ContainerPort] = [
                V1ContainerPort(container_port=target_port)
                for target_port in data.target_ports
            ]

            # create pod manifest
            pod_manifest: V1Pod = V1Pod(
                metadata=V1ObjectMeta(name=data.pod_name),
                spec=V1PodSpec(
                    containers=[
                        V1Container(
                            name=data.pod_name,
                            image=data.image_name,
                            ports=target_ports,
                            env=environment_variables,
                        )
                    ]
                )
            )
            # create the actual pod
            pod: V1Pod = cls.client.create_namespaced_pod(data.namespace_name, pod_manifest)
            return {
                "pod_id": pod.metadata.uid,
                "pod_name": pod.metadata.name,
                "pod_namespace": pod.metadata.namespace,
            }
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, pod_name: str, timeout_seconds: float = 2.0) -> None:
        is_terminated: bool = False
        while is_terminated != True:
            pods: list[dict] = cls.list(ListPodDataClass(**{'namespace_name': namespace_name}))
            found: bool = False
            for pod in pods:
                if pod.metadata.name == pod_name:
                    found = True
                    break
            is_terminated = not found
            print(f'Pod: {pod_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeletePodDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            cls.client.delete_namespaced_pod(data.pod_name, data.namespace_name)
            cls.poll_termination(data.namespace_name, data.pod_name) # wait for pod to be deleted, otherwise list pod will find it and integration tests will fail..
            return {'status': 'success'}
        except ApiException as ae:
            raise ApiException(f'Error occured while deleting pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e
