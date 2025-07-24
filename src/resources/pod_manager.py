# modules
import time
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.get_pod_dataclass import GetPodDataClass
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.resources.resource_config import POD_IP_TIMEOUT_SECONDS, POD_UPTIME_TIMEOUT, POD_TERMINATION_TIMEOUT
from src.resources.resource_config import SNAPSHOT_DIR, SNAPSHOT_FILE_NAME, SNAPSHOT_SIDECAR_NAME, SNAPSHOT_SIDECAR_IMAGE_NAME
from src.common.config import REPO_NAME, REPO_PASSWORD

# third party
from kubernetes.client.rest import ApiException
from kubernetes.client import V1EnvVar
from kubernetes.client import V1ContainerPort
from kubernetes.client import V1Pod
from kubernetes.client import V1ObjectMeta
from kubernetes.client import V1PodSpec
from kubernetes.client import V1Container
from kubernetes.client import V1SecurityContext
from kubernetes.client import V1Volume
from kubernetes.client import V1EmptyDirVolumeSource
from kubernetes.client import V1VolumeMount
from kubernetes.stream import stream

# NOTE: Check if sidecar and main pod share a snapshot volume in SaveUtility.
class SaveUtility(KubernetesResourceManager):
    '''
    Utility class for saving a pod.
    This class assumes that all containers and pods are available.
    This is because we cannot use PodManager because PodManager uses this utility.
    That is a cyclic dependency.

    Therefore, make sure all containers (i.e. main containers and sidecars) are available before calling this utility.
    '''

    @classmethod
    def run_command(cls, pod_name: str, namespace_name: str, container_name: str, command: str) -> str:
        '''
        Exec a command into a pod container and return the output.
        :params: pod_name: str - Name of the pod
        :params: namespace_name: str - Name of the namespace  
        :params: container_name: str - Name of the container within the pod
        :params: command: str - Command to execute
        :returns: str - Command output
        '''
        try:
            cls.check_kubernetes_client()
            result = stream(
                cls.client.connect_get_namespaced_pod_exec,
                pod_name,
                namespace_name,
                container=container_name,
                command=["/bin/bash", "-c", command],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False
            )
            return result
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def check_shared_volume(cls, data: SavePodDataClass) -> bool:
        '''
        Check if the sidecar and main containers share a volume.
        Both containers are in the same pod but we verify they can access the same volume.
        :params: data: SavePodDataClass
        :returns: bool: True if volume is shared, False otherwise
        '''
        try:
            cls.check_kubernetes_client()
            # check if the sidecar and main container share a volume
            check_shared_volume_cmd: str = (
                f"ls -l {SNAPSHOT_DIR}"
            )
            breakpoint()
            # Both containers are in the same pod (data.pod_name)
            # but we exec into different containers
            sidecar_response: str = cls.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, check_shared_volume_cmd)
            main_response: str = cls.run_command(data.pod_name, data.namespace_name, data.pod_name, check_shared_volume_cmd)
            if sidecar_response == main_response:
                return True
            return False
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def build_tar(cls, data: SavePodDataClass) -> None:
        '''
        Build a tar file of the main container's filesystem.
        :params: data: SavePodDataClass
        :returns: None
        '''
        try:
            cls.check_kubernetes_client()
            # build the tar file
            tar_cmd: str = (
                f"tar --exclude=/proc --exclude=/sys --exclude=/dev --exclude={SNAPSHOT_DIR} "
                f"-czvf {SNAPSHOT_DIR}/{SNAPSHOT_FILE_NAME}.tar.gz /"
            )
            cls.run_command(data.pod_name, data.namespace_name, data.pod_name, tar_cmd)
            print(f"{data.pod_name}: Filesystem snapshot created in main container.")
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def unpack_tar(cls, data: SavePodDataClass) -> None:
        '''
        Unpack the tar file. This is done in the sidecar pod.
        Prerequisites:
        - A tar file should exist.
        :params: data: SavePodDataClass
        :returns: None
        '''
        try:
            cls.check_kubernetes_client()
            # unpack the tar file
            untar_cmd: str = (
                f"mkdir -p {SNAPSHOT_DIR}/rootfs && "
                f"tar -xzvf {SNAPSHOT_DIR}/{SNAPSHOT_FILE_NAME}.tar.gz -C {SNAPSHOT_DIR}/rootfs"
            )
            cls.run_command(data.sidecar_pod_name, data.namespace_name, data.sidecar_pod_name, untar_cmd)
            print(f"{data.sidecar_pod_name}: Filesystem snapshot unpacked into sidecar pod.")
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def create_dockerfile(cls, data: SavePodDataClass) -> None:
        '''
        Create a Dockerfile in the sidecar pod. This is done in the sidecar pod.
        Prerequisites:
        - The rootfs directory should exist.
        :params: data: SavePodDataClass
        :returns: None
        '''
        try:
            dockerfile_content: str = (
                    "FROM scratch\n"
                    "COPY . /\n"
                    "ENTRYPOINT [\"/entrypoint.sh\"]\n"
                )
            echo_dockerfile_cmd: str = f"echo '{dockerfile_content}' > {SNAPSHOT_DIR}/rootfs/Dockerfile"
            cls.run_command(data.sidecar_pod_name, data.namespace_name, data.sidecar_pod_name, echo_dockerfile_cmd)
            print(f"{data.sidecar_pod_name}: Dockerfile written.")
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def build_image(cls, data: SavePodDataClass) -> dict:
        '''
        Build an image from the rootfs directory.
        Prerequisites:
        - The Dockerfile should exist.
        :params: data: SavePodDataClass
        :returns: dict: Image name
        '''
        try:
            cls.check_kubernetes_client()
            image_name: str = f'{data.pod_name}-image:latest'
            # build the image
            build_image_cmd: str = (
                f"docker build -t {image_name} -f {SNAPSHOT_DIR}/rootfs/Dockerfile {SNAPSHOT_DIR}/rootfs"
            )
            cls.run_command(data.sidecar_pod_name, data.namespace_name, data.sidecar_pod_name, build_image_cmd)
            print(f"{data.sidecar_pod_name}: Image built.")
            return {
                'image_name': image_name
            }
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def tag_image(cls, data: SavePodDataClass, image_name: str, repo_name: str) -> None:
        '''
        Tag the image.
        :params: data: SavePodDataClass
        :params: image_name: str
        :returns: None
        '''
        try:
            cls.check_kubernetes_client()
            # tag the image
            tag_image_cmd: str = (
                f"docker tag {image_name} {repo_name}/{image_name}"
            )
            cls.run_command(data.sidecar_pod_name, data.namespace_name, data.sidecar_pod_name, tag_image_cmd)
            print(f"{data.sidecar_pod_name}: Image tagged.")
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def docker_login(cls, data: SavePodDataClass, repo_name: str, repo_password: str) -> None:
        '''
        Login to the docker registry.
        :params:
            data: SavePodDataClass
            repo_name: str
            repo_password: str
        :returns: None
        '''
        try:
            cls.check_kubernetes_client()
            # login to the docker registry
            login_cmd: str = (
                f"docker login -u {repo_name} -p {repo_password}"
            )
            cls.run_command(data.sidecar_pod_name, data.namespace_name, data.sidecar_pod_name, login_cmd)
            print(f"{data.sidecar_pod_name}: Docker registry logged in.")
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def docker_push(cls, data: SavePodDataClass, image_name: str, repo_name: str) -> None:
        '''
        Push the image to the docker registry.
        :params:
            data: SavePodDataClass
            image_name: str
            repo_name: str
        :returns: None
        '''
        try:
            cls.check_kubernetes_client()
            # push the image
            push_cmd: str = (
                f"docker push {repo_name}/{image_name}"
            )
            cls.run_command(data.sidecar_pod_name, data.namespace_name, data.sidecar_pod_name, push_cmd)
            print(f"{data.sidecar_pod_name}: Image pushed to docker registry.")
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def save_image(cls, data: SavePodDataClass) -> dict:
        '''
        Save the pod.
        :params: data: SavePodDataClass
        :returns: dict: Image name
        '''
        try:
            cls.check_kubernetes_client()
            repo_name: str = REPO_NAME
            repo_password: str = REPO_PASSWORD
            if not repo_name or not repo_password:
                raise Exception('REPO_NAME or REPO_PASSWORD is not set')
            # check if the sidecar and main pod share a volume
            if not cls.check_shared_volume(data):
                raise ApiException(f'Sidecar and main pod do not share a volume')
            # build the tar file
            cls.build_tar(data)
            # unpack the tar file
            cls.unpack_tar(data)
            # create the dockerfile
            cls.create_dockerfile(data)
            # build the image
            image_name: dict = cls.build_image(data)
            # tag the image
            cls.tag_image(data, image_name['image_name'], repo_name)
            # login to the docker registry
            cls.docker_login(data, repo_name, repo_password)
            # push the image
            cls.docker_push(data, image_name['image_name'], repo_name)
            return image_name
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e


class PodManager(KubernetesResourceManager):
    '''
    Manage kubernetes pods.
    '''

    @classmethod
    def get_container_ports(cls, container: V1Container) -> list[dict]:
        """
        Get ports of a single container as a list of dictionaries.

        Args:
            container: V1Container object.

        Returns:
            List of ports with name, container_port, and protocol.
        """
        ports: list[dict] = []
        if container.ports:
            for port in container.ports:
                ports.append({
                    'name': port.name if port.name else None,
                    'container_port': port.container_port,
                    'protocol': port.protocol
                })
        return ports

    @classmethod
    def get_pod_ports(cls, pod: V1Pod) -> list[dict]:
        """
        Get all ports configured for a pod's containers
        """
        ports: list[dict] = []
        for container in pod.spec.containers:
            if container.ports:
                for port in container.ports:
                    ports.append({
                        'name': port.name if port.name else None,
                        'container_port': port.container_port,
                        'protocol': port.protocol
                    })
        return ports

    @classmethod
    def get_pod_containers(cls, pod: V1Pod) -> list[dict]:
        """
        Get all containers for a pod
        """
        if not pod.spec.containers:
            return []
        return [
            {
                'container_name': container.name,
                'container_image': container.image,
                'container_ports': cls.get_container_ports(container)
            }
            for container in pod.spec.containers
        ]

    @classmethod
    def get_pod_response(cls, pod: V1Pod) -> dict:
        return {
            'pod_id': pod.metadata.uid,
            'pod_name': pod.metadata.name,
            'pod_namespace': pod.metadata.namespace,
            'pod_ip': cls.get_pod_ip(pod.metadata.namespace, pod.metadata.name),
            'pod_ports': cls.get_pod_ports(pod),
            'pod_labels': pod.metadata.labels or {},
            'pod_containers': cls.get_pod_containers(pod),
        }

    @classmethod
    def list(cls, data: ListPodDataClass) -> list[dict]:
        try:
            cls.check_kubernetes_client()
            return [
                cls.get_pod_response(pod)
                for pod in cls.client.list_namespaced_pod(namespace=data.namespace_name).items
            ]
        except ApiException as ae:
            raise ApiException(f'Error occurred while listing pods: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get(cls, data: GetPodDataClass) -> dict:
        '''
        Get a pod.
        :params: data: GetPodDataClass
        :returns: dict: Pod Details
        '''
        try:
            cls.check_kubernetes_client()
            response: V1Pod = cls.client.read_namespaced_pod(name=data.pod_name, namespace=data.namespace_name)
            return cls.get_pod_response(response)
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occurred while getting pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def get_pod_ip(cls, namespace_name: str, pod_name: str, timeout_seconds: float = POD_IP_TIMEOUT_SECONDS) -> str:
        '''
        Get the IP of the Pod.
        '''
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)
                if pod.status.pod_ip:
                    print(f'Pod: {pod_name} IP:', pod.status.pod_ip)
                    return pod.status.pod_ip
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for pod {pod_name} IP address after {timeout_seconds} seconds")

    @classmethod
    def poll_status(cls, namespace_name: str, pod_name: str, target_status: str, timeout_seconds: float = POD_UPTIME_TIMEOUT) -> None:
        '''
        Poll pod status until it matches target_status or timeout is reached.
        
        Args:
            namespace_name: Name of the namespace
            pod_name: Name of the pod
            target_status: Status to wait for (e.g., 'Running', 'Succeeded')
            timeout_seconds: Maximum time to wait in seconds
        
        Raises:
            TimeoutError: If pod doesn't reach target status within timeout
            ApiException: If there's an error getting pod status
        '''
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)
                current_status = pod.status.phase
                print(f'Pod: {pod_name} Status:', current_status)
                if current_status == target_status:
                    return
                elif current_status in ['Failed', 'Unknown']:
                    raise Exception(f'Pod entered {current_status} state')
            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for pod {pod_name} to reach status {target_status} after {timeout_seconds} seconds")

    @classmethod
    def save(cls, data: SavePodDataClass) -> dict:
        '''
        Save the pod.
        :params: data: SavePodDataClass
        :returns: dict: Pod Details
        '''
        try:
            cls.check_kubernetes_client()
            # get the pod
            pod: V1Pod = cls.get(GetPodDataClass(namespace_name=data.namespace_name, pod_name=data.pod_name))
            # Pod not found
            if pod == {}:
                raise ApiException(f'Pod {data.pod_name} not found')
            # Pod has no containers
            if pod['pod_containers'] == []:
                raise ApiException(f'Pod {data.pod_name} has no containers')
            # Pod needs a main container and a sidecar container
            if len(pod['pod_containers']) != 2:
                raise ApiException(f'Pod {data.pod_name} needs a main container and a sidecar container')
            container_names: list[str] = [container['container_name'] for container in pod['pod_containers']]
            if SNAPSHOT_SIDECAR_NAME not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a sidecar container')
            if data.pod_name not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a main container')
            # save the pod
            return SaveUtility.save_image(data)
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Error occured: {str(e)}') from e

    @classmethod
    def create(cls, data: CreatePodDataClass) -> dict:
        try:
            cls.check_kubernetes_client()
            p: dict = cls.get(GetPodDataClass(namespace_name=data.namespace_name, pod_name=data.pod_name))
            if p:
                return p
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
            # Create volume mounts for snapshot directory
            snapshot_volume_mount = V1VolumeMount(
                name="snapshot-volume",
                mount_path=SNAPSHOT_DIR
            )
            containers: list[V1Container] = [
                V1Container(
                    name=data.pod_name,
                    image=data.image_name,
                    ports=target_ports,
                    env=environment_variables,
                    security_context=V1SecurityContext(
                        privileged=True
                    ),
                    volume_mounts=[snapshot_volume_mount]
                ),
                V1Container(
                    name=SNAPSHOT_SIDECAR_NAME,
                    image=SNAPSHOT_SIDECAR_IMAGE_NAME,
                    security_context=V1SecurityContext(
                        privileged=True
                    ),
                    volume_mounts=[snapshot_volume_mount]
                )
            ]
            # Create volumes for the pod
            volumes = [
                V1Volume(
                    name="snapshot-volume",
                    empty_dir=V1EmptyDirVolumeSource()
                )
            ]

            # create pod manifest
            pod_manifest: V1Pod = V1Pod(
                metadata=V1ObjectMeta(
                    name=data.pod_name,
                    labels={"app": data.pod_name},
                    annotations={
                        "nginx.org/websocket-services": data.pod_name,  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-read-timeout": "3600",  # for websockets
                        "nginx.ingress.kubernetes.io/proxy-send-timeout": "3600"  # for websockets
                    }
                ),
                spec=V1PodSpec(
                    security_context=V1SecurityContext(
                        privileged=True
                    ),
                    volumes=volumes,
                    containers=containers
                )
            )
            # create the actual pod
            pod: V1Pod = cls.client.create_namespaced_pod(data.namespace_name, pod_manifest)
            # wait for the pod status to be running
            cls.poll_status(namespace_name=data.namespace_name, pod_name=data.pod_name, target_status='Running')
            return cls.get_pod_response(pod)
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, pod_name: str, timeout_seconds: float = POD_TERMINATION_TIMEOUT) -> None:
        is_terminated: bool = False
        while is_terminated != True:
            pod: dict = cls.get(GetPodDataClass(**{'namespace_name': namespace_name, 'pod_name': pod_name}))
            is_terminated = (pod == {})
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
