# modules
import time
import gc  # this is because we use the stream function which does not close sockets properly. So we manually collect them using gc.
import warnings  # this is to capture resource warnings.
from typing import List
from src.resources.dataclasses.pod.delete_pod_dataclass import DeletePodDataClass
from src.resources.dataclasses.pod.get_pod_dataclass import GetPodDataClass
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.pod.create_pod_dataclass import CreatePodDataClass, ResourceRequirementsDataClass
from src.resources.dataclasses.pod.list_pod_dataclass import ListPodDataClass
from src.resources.dataclasses.pod.save_pod_dataclass import SavePodDataClass
from src.common.exceptions import UnsupportedRuntimeEnvironment
from src.resources.resource_config import IMAGE_PUSH_TIMEOUT_MINUTES, POD_IP_TIMEOUT_SECONDS, POD_UPTIME_TIMEOUT, POD_TERMINATION_TIMEOUT, IMAGE_BUILD_TIMEOUT_MINUTES, STATUS_SIDECAR_IMAGE_NAME, STATUS_SIDECAR_NAME, CONTAINER_READINESS_TIMEOUT_SECONDS, DOCKER_LOGIN_MAX_RETRIES, DOCKER_LOGIN_RETRY_DELAY_SECONDS, DOCKER_BUILD_MAX_RETRIES, DOCKER_BUILD_RETRY_DELAY_SECONDS
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
from kubernetes.client import V1ResourceRequirements
from kubernetes.stream import ws_client
from kubernetes.stream import stream


class ExecUtility(KubernetesResourceManager):
    '''
    Utility class for executing commands in a pod.
    '''

    @classmethod
    def run_command(cls, pod_name: str, namespace_name: str, container_name: str, command: str) -> str:
        '''
        Exec a command into a pod container and return the output
        :params: pod_name: str - Name of the pod
        :params: namespace_name: str - Name of the namespace  
        :params: container_name: str - Name of the container within the pod
        :params: command: str - Command to execute
        :returns: str - Command output
        '''
        try:
            cls.check_kubernetes_client()

            # Temporarily suppress the specific ResourceWarning
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*ssl.SSLSocket.*")
                # For simple output, use preload_content=True
                output: str = stream(
                    cls.client.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace_name,
                    container=container_name,
                    command=["/bin/bash", "-c", command],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=True
                )
                # Force garbage collection to clean up any lingering connections
                gc.collect()
            return output.strip() if output else "" 
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while executing command in pod: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Unknown error occured: {str(e)}') from e

    @classmethod
    def run_command_with_stream(cls, pod_name: str, namespace_name: str, container_name: str, command: str, timeout_minutes: int = 10) -> str:
        '''
        Exec a command into a pod container with real-time streaming output.
        :params: pod_name: str - Name of the pod
        :params: namespace_name: str - Name of the namespace  
        :params: container_name: str - Name of the container within the pod
        :params: command: str - Command to execute
        :params: timeout_minutes: int - Maximum time to wait for command completion
        :returns: str - Complete command output
        '''
        try:
            cls.check_kubernetes_client()
            # Suppress ResourceWarning for streaming connections
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*ssl.SSLSocket.*")
                # Create WebSocket connection with _preload_content=False for streaming
                stream_client: ws_client.WSClient = stream(
                    cls.client.connect_get_namespaced_pod_exec,
                    pod_name,
                    namespace_name,
                    container=container_name,
                    command=["/bin/bash", "-c", command],
                    stderr=True,
                    stdin=False,
                    stdout=True,
                    tty=False,
                    _preload_content=False  # This gives us a WebSocket client for streaming
                )
                try:
                    output: str = ""
                    start_time: float = time.time()
                    timeout_seconds: float = timeout_minutes * 60
                    while stream_client.is_open():
                        # Check for timeout
                        if time.time() - start_time > timeout_seconds:
                            raise TimeoutError(f"Command timed out after {timeout_minutes} minutes")
                        stream_client.update(timeout=5)
                        if stream_client.peek_stdout():
                            stdout_chunk: str = stream_client.read_stdout()
                            output += stdout_chunk
                            if stdout_chunk.strip():
                                print(f"[{container_name}] {stdout_chunk.strip()}")
                        if stream_client.peek_stderr():
                            stderr_chunk: str = stream_client.read_stderr()
                            output += stderr_chunk
                            if stderr_chunk.strip():
                                print(f"[{container_name}] {stderr_chunk.strip()}")
                    return output.strip()
                finally:
                    # Always close the stream client
                    try:
                        stream_client.close()
                    except Exception:
                        pass
                    # Force garbage collection to clean up any lingering connections
                    gc.collect()
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while executing command in pod: {str(ae)}') from ae
        except Exception as e:
            raise Exception(f'Unknown error occured: {str(e)}') from e


class SaveUtility(KubernetesResourceManager):
    '''
    Utility class for saving a pod.
    This class assumes that all containers and pods are available.
    This is because we cannot use PodManager because PodManager uses this utility.
    That is a cyclic dependency.

    Therefore, make sure all containers (i.e. main containers and sidecars) are available before calling this utility.
    '''

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
            # Both containers are in the same pod (data.pod_name)
            # but we exec into different containers
            sidecar_response: str = ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, check_shared_volume_cmd)
            main_response: str = ExecUtility.run_command(data.pod_name, data.namespace_name, data.pod_name, check_shared_volume_cmd)
            
            # Check if both commands return the same output
            # Basically, both containers should have the volume and return: total 0,
            # If they don't have it, the command returns: No such file or directory
            if sidecar_response != main_response:
                return False
            return True
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
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.pod_name, tar_cmd)
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
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, untar_cmd)
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
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, echo_dockerfile_cmd)
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
        Build an image from the rootfs directory with retry logic for reliability.
        Prerequisites:
        - The Dockerfile should exist.
        :params: data: SavePodDataClass
        :returns: dict: Image name and build output
        '''
        cls.check_kubernetes_client()
        image_name: str = f'{data.pod_name}-image:latest'

        # build the image with verbose output
        build_image_cmd: str = (
            f"docker image build -t {image_name} -f {SNAPSHOT_DIR}/rootfs/Dockerfile {SNAPSHOT_DIR}/rootfs"
        )

        last_error = None

        # Retry logic with exponential backoff
        for attempt in range(1, DOCKER_BUILD_MAX_RETRIES + 1):
            try:
                print(f"{data.sidecar_pod_name}: Starting image build (attempt {attempt}/{DOCKER_BUILD_MAX_RETRIES})...")
                build_output = ExecUtility.run_command_with_stream(data.pod_name, data.namespace_name, data.sidecar_pod_name, build_image_cmd, timeout_minutes=IMAGE_BUILD_TIMEOUT_MINUTES)

                # Check for success indicators in the output
                success_indicators = ["Successfully built", "Successfully tagged"]
                if any(indicator in build_output for indicator in success_indicators):
                    print(f"{data.sidecar_pod_name}: Image built successfully.")
                    # Verify the image actually exists
                    verify_cmd = f"docker images {image_name} --format 'table {{{{.Repository}}}}:{{{{.Tag}}}}'"
                    verify_output = ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, verify_cmd)
                    if image_name in verify_output:
                        print(f"{data.sidecar_pod_name}: Image verified: {image_name}")
                        return {
                            'image_name': image_name,
                            'build_output': build_output
                        }
                    else:
                        last_error = Exception(f"Image {image_name} was not found after build (verification failed)")
                        if attempt < DOCKER_BUILD_MAX_RETRIES:
                            delay = DOCKER_BUILD_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                            print(f"{data.sidecar_pod_name}: Image verification failed (attempt {attempt}/{DOCKER_BUILD_MAX_RETRIES}). Retrying in {delay} seconds...")
                            time.sleep(delay)
                            continue
                        raise last_error
                else:
                    # No success indicators found - build likely failed
                    print(f"{data.sidecar_pod_name}: Build output:\n{build_output}")
                    last_error = Exception(f"Docker build failed - no success indicators found. See output above for details.")
                    if attempt < DOCKER_BUILD_MAX_RETRIES:
                        delay = DOCKER_BUILD_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                        print(f"{data.sidecar_pod_name}: Docker build failed (attempt {attempt}/{DOCKER_BUILD_MAX_RETRIES}). Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    raise last_error
            except TimeoutError as te:
                last_error = te
                if attempt < DOCKER_BUILD_MAX_RETRIES:
                    delay = DOCKER_BUILD_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    print(f"{data.sidecar_pod_name}: Docker build timed out (attempt {attempt}/{DOCKER_BUILD_MAX_RETRIES}). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise TimeoutError(te) from te
            except ApiException as ae:
                last_error = ae
                if attempt < DOCKER_BUILD_MAX_RETRIES:
                    delay = DOCKER_BUILD_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    print(f"{data.sidecar_pod_name}: Docker build API error (attempt {attempt}/{DOCKER_BUILD_MAX_RETRIES}). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise ApiException(f'Error occured while building image: {str(ae)}') from ae
            except UnsupportedRuntimeEnvironment as ure:
                # Don't retry for unsupported runtime - it won't change
                raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
            except Exception as e:
                last_error = e
                if attempt < DOCKER_BUILD_MAX_RETRIES:
                    delay = DOCKER_BUILD_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    print(f"{data.sidecar_pod_name}: Docker build error (attempt {attempt}/{DOCKER_BUILD_MAX_RETRIES}): {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise Exception(f'Docker build error: {str(e)}') from e

        # If we get here, all retries failed
        print(f"{data.sidecar_pod_name}: Docker build failed after {DOCKER_BUILD_MAX_RETRIES} attempts.")
        raise Exception(f'Docker build error: {str(last_error)}') from last_error

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
                f"docker image tag {image_name} {repo_name}/{image_name}"
            )
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, tag_image_cmd)
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
    def docker_login(cls, data: SavePodDataClass, repo_name: str, repo_password: str) -> bool:
        '''
        Login to the docker registry with retry logic for reliability.
        :params:
            data: SavePodDataClass
            repo_name: str
            repo_password: str
        :returns: bool: True if login succeeded, False otherwise
        '''
        cls.check_kubernetes_client()
        login_cmd: str = (
            f"docker login -u {repo_name} -p {repo_password}"
        )

        # Retry logic with exponential backoff
        for attempt in range(1, DOCKER_LOGIN_MAX_RETRIES + 1):
            try:
                print(f"{data.sidecar_pod_name}: Attempting docker login (attempt {attempt}/{DOCKER_LOGIN_MAX_RETRIES})...")
                docker_login_output: str = ExecUtility.run_command_with_stream(
                    data.pod_name, 
                    data.namespace_name, 
                    data.sidecar_pod_name, 
                    login_cmd
                )
                if 'Login Succeeded' in docker_login_output:
                    print(f"{data.sidecar_pod_name}: Docker registry logged in successfully.")
                    return True
                # Check for specific error messages that indicate we should retry
                retryable_errors = [
                    'error',
                    'timeout',
                    'connection',
                    'network',
                    'unauthorized',
                    'authentication'
                ]
                output_lower = docker_login_output.lower()
                should_retry = any(error in output_lower for error in retryable_errors) and attempt < DOCKER_LOGIN_MAX_RETRIES
                if should_retry:
                    delay = DOCKER_LOGIN_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))  # Exponential backoff
                    print(f"{data.sidecar_pod_name}: Docker login failed (attempt {attempt}/{DOCKER_LOGIN_MAX_RETRIES}). Retrying in {delay} seconds...")
                    print(f"{data.sidecar_pod_name}: Error output: {docker_login_output[:200]}...")  # Print first 200 chars
                    time.sleep(delay)
                    continue
                else:
                    print(f"{data.sidecar_pod_name}: Docker registry login failed after {attempt} attempts. Output: {docker_login_output[:500]}")
                    return False
            except TimeoutError as te:
                if attempt < DOCKER_LOGIN_MAX_RETRIES:
                    delay = DOCKER_LOGIN_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    print(f"{data.sidecar_pod_name}: Docker login timed out (attempt {attempt}/{DOCKER_LOGIN_MAX_RETRIES}). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise TimeoutError(te) from te
            except ApiException as ae:
                if attempt < DOCKER_LOGIN_MAX_RETRIES:
                    delay = DOCKER_LOGIN_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    print(f"{data.sidecar_pod_name}: Docker login API error (attempt {attempt}/{DOCKER_LOGIN_MAX_RETRIES}). Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise ApiException(f'Error occured during docker login: {str(ae)}') from ae
            except Exception as e:
                if attempt < DOCKER_LOGIN_MAX_RETRIES:
                    delay = DOCKER_LOGIN_RETRY_DELAY_SECONDS * (2 ** (attempt - 1))
                    print(f"{data.sidecar_pod_name}: Docker login error (attempt {attempt}/{DOCKER_LOGIN_MAX_RETRIES}): {str(e)}. Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise Exception(f'Unknown error occured: {str(e)}') from e
        # If we get here, all retries failed
        print(f"{data.sidecar_pod_name}: Docker registry login failed after {DOCKER_LOGIN_MAX_RETRIES} attempts.")
        return False

    @classmethod
    def docker_push(cls, data: SavePodDataClass, image_name: str, repo_name: str) -> bool:
        '''
        Push the image to the docker registry.
        :params:
            data: SavePodDataClass
            image_name: str
            repo_name: str
        :returns: bool: True if push succeeded, False otherwise
        '''
        try:
            cls.check_kubernetes_client()
            # push the image
            push_cmd: str = (
                f"docker image push {repo_name}/{image_name}"
            )
            push_output: str = ExecUtility.run_command_with_stream(data.pod_name, data.namespace_name, data.sidecar_pod_name, push_cmd, timeout_minutes=IMAGE_PUSH_TIMEOUT_MINUTES)
            if 'Pushed' in push_output:
                print(f"{data.sidecar_pod_name}: Image pushed to docker registry.")
                return True
            print(f"{data.sidecar_pod_name}: Docker registry push failed. See output above for details.")
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
    def delete_local_image(cls, data: SavePodDataClass, image_name: str, repo_name: str) -> bool:
        '''
        Delete the image from local Docker daemon to free up space.
        :params:
            data: SavePodDataClass
            image_name: str - Local image name (e.g., "test-pod-image:latest")
            repo_name: str - Repository name (e.g., "zim95")
        :returns: bool: True if deletion succeeded, False otherwise
        '''
        try:
            cls.check_kubernetes_client()
            
            # Create both image references to delete
            local_image = image_name
            tagged_image = f"{repo_name}/{image_name}"
            
            # Delete both local and tagged versions
            delete_cmd: str = f"docker rmi {local_image} {tagged_image}"
            
            ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, delete_cmd)
            print(f"{data.sidecar_pod_name}: Local images deleted: {local_image}, {tagged_image}")
            
            # Verify deletion by checking if images still exist
            verify_cmd = f"docker images --format '{{{{.Repository}}}}:{{{{.Tag}}}}' | grep -E '^({local_image}|{tagged_image})$'"
            try:
                verify_output = ExecUtility.run_command(data.pod_name, data.namespace_name, data.sidecar_pod_name, verify_cmd)
                if verify_output.strip():
                    print(f"{data.sidecar_pod_name}: Warning - Some images may not have been deleted: {verify_output}")
                    return False
                else:
                    print(f"{data.sidecar_pod_name}: Image deletion verified.")
                    return True
            except Exception:
                # If grep finds nothing, it returns non-zero exit code, which means deletion was successful
                print(f"{data.sidecar_pod_name}: Image deletion verified.")
                return True
                
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while deleting local image: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            print(f'Warning: Failed to delete local images {image_name}: {str(e)}')
            return False

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
            is_logged_in: bool = cls.docker_login(data, repo_name, repo_password)
            if not is_logged_in:
                raise Exception('Docker registry login failed')
            # push the image
            is_pushed: bool = cls.docker_push(data, image_name['image_name'], repo_name)
            if not is_pushed:
                raise Exception('Docker registry push failed')
            # delete local images to free up space
            is_deleted: bool = cls.delete_local_image(data, image_name['image_name'], repo_name)
            if not is_deleted:
                raise Exception('Local images deletion failed')
            return {
                'image_name': image_name['image_name']
            }
        except TimeoutError as te:
            raise TimeoutError(te) from te
        except ApiException as ae:
            raise ApiException(f'Error occured while creating pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Save pod error occured: {str(e)}') from e


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
        Get all ports configured for a pod's containers.
        :params: pod: V1Pod
        :returns: list[dict]: List of ports
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
        Get all containers for a pod.
        :params: pod: V1Pod
        :returns: list[dict]: List of containers
        """
        if not pod.spec.containers:
            return []

        containers: list[dict] = []

        # snapshot_size_limit is a property of the EmptyDir volume, not a
        # Kubernetes compute resource. Derive it once from the pod's volumes
        # (e.g. the "snapshot-volume" EmptyDir.size_limit) and then attach it
        # to each container's resource view for convenience.
        snapshot_size_limit: str | None = None
        if pod.spec.volumes:
            for volume in pod.spec.volumes:
                empty_dir: V1EmptyDirVolumeSource | None = getattr(volume, "empty_dir", None)
                if empty_dir is not None and getattr(empty_dir, "size_limit", None):
                    # If multiple volumes exist, we take the first one that has a size_limit.
                    snapshot_size_limit = empty_dir.size_limit
                    break

        for container in pod.spec.containers:
            # Derive per-container compute resources from the Kubernetes spec
            resources: V1ResourceRequirements = container.resources or V1ResourceRequirements()
            requests: dict | None = getattr(resources, "requests", None)
            limits: dict | None = getattr(resources, "limits", None)
            container_resources: dict = {
                'cpu_request': (requests or {}).get('cpu'),
                'cpu_limit': (limits or {}).get('cpu'),
                'memory_request': (requests or {}).get('memory'),
                'memory_limit': (limits or {}).get('memory'),
                'ephemeral_request': (requests or {}).get('ephemeral-storage'),
                'ephemeral_limit': (limits or {}).get('ephemeral-storage'),
                # Not a native container resource; exposed here as a convenience
                # and derived from the pod's EmptyDir volume.
                'snapshot_size_limit': snapshot_size_limit,
            }

            containers.append(
                {
                    'resource_type': 'pod_container',
                    'container_name': container.name,
                    'container_image': container.image,
                    'container_ports': cls.get_container_ports(container),
                    'container_resources': container_resources,
                }
            )
        return containers

    @classmethod
    def get_pod_response(cls, pod: V1Pod) -> dict:
        '''
        Get the pod response.
        :params: pod: V1Pod
        :returns: dict: Pod Details
        '''
        return {
            'resource_type': 'pod',
            'pod_id': pod.metadata.uid,
            'pod_name': pod.metadata.name,
            'pod_namespace': pod.metadata.namespace,
            'pod_ip': cls.get_pod_ip(pod.metadata.namespace, pod.metadata.name),
            'pod_ports': cls.get_pod_ports(pod),
            'pod_labels': pod.metadata.labels or {},
            'associated_resources': cls.get_pod_containers(pod),
        }

    @classmethod
    def list(cls, data: ListPodDataClass) -> list[dict]:
        '''
        List all pods in a namespace.
        :params: data: ListPodDataClass
        :returns: list[dict]: List of pods
        '''
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
        :params: namespace_name: str
        :params: pod_name: str
        :params: timeout_seconds: float
        :returns: str: Pod IP
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
    def poll_container_readiness(cls, namespace_name: str, pod_name: str, container_names: List[str], timeout_seconds: float = CONTAINER_READINESS_TIMEOUT_SECONDS) -> None:
        '''
        Poll container statuses until all specified containers are running or timeout is reached.

        Args:
            namespace_name: Name of the namespace
            pod_name: Name of the pod
            container_names: List of container names to check
            timeout_seconds: Maximum time to wait in seconds

        Raises:
            TimeoutError: If containers don't become running within timeout
            ApiException: If there's an error getting pod status
        '''
        start_time = time.time()
        while (time.time() - start_time) < timeout_seconds:
            try:
                pod = cls.client.read_namespaced_pod(name=pod_name, namespace=namespace_name)

                # Check if pod is running first
                if pod.status.phase != 'Running':
                    time.sleep(1)
                    continue

                # Build a map of container statuses
                container_statuses = {}
                if pod.status.container_statuses:
                    for status in pod.status.container_statuses:
                        container_statuses[status.name] = status

                # Check if all required containers are running
                all_running = True
                for container_name in container_names:
                    if container_name not in container_statuses:
                        all_running = False
                        break
                    status = container_statuses[container_name]
                    # Check if container state has 'running' attribute (meaning it's running)
                    if not hasattr(status, 'state') or not status.state:
                        all_running = False
                        break
                    # Check if state.running exists (container is running)
                    # V1ContainerState has attributes: running, waiting, terminated
                    if not hasattr(status.state, 'running') or status.state.running is None:
                        all_running = False
                        break

                if all_running:
                    print(f'All containers in pod {pod_name} are running')
                    return

            except ApiException as e:
                if e.status != 404:  # Ignore 404 errors while pod is being created
                    raise
            time.sleep(1)
        raise TimeoutError(f"Timeout waiting for containers {container_names} in pod {pod_name} to be running after {timeout_seconds} seconds")

    @classmethod
    def save(cls, data: SavePodDataClass) -> dict:
        '''
        Save the pod.
        :params: data: SavePodDataClass
        :returns: dict: Image details
        '''
        try:
            cls.check_kubernetes_client()
            # get the pod
            pod: V1Pod = cls.get(GetPodDataClass(namespace_name=data.namespace_name, pod_name=data.pod_name))
            # Pod not found
            if pod == {}:
                raise ApiException(f'Pod {data.pod_name} not found')
            # Pod has no containers
            if pod['associated_resources'] == []:
                raise ApiException(f'Pod {data.pod_name} has no containers')
            # Pod needs a main container and two sidecar containers
            if len(pod['associated_resources']) != 3:
                raise ApiException(f'Pod {data.pod_name} needs a main container, sidecar container and status sidecar container')
            container_names: list[str] = [container['container_name'] for container in pod['associated_resources']]
            if SNAPSHOT_SIDECAR_NAME not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a snapshot sidecar container')
            if STATUS_SIDECAR_NAME not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a status sidecar container')
            if data.pod_name not in container_names:
                raise ApiException(f'Pod {data.pod_name} needs a main container, status sidecar container and snapshot sidecar container')

            # Wait for all containers to be running before attempting to save
            # This prevents "container not running" errors during save operations
            required_containers = [data.pod_name, data.sidecar_pod_name]
            cls.poll_container_readiness(
                namespace_name=data.namespace_name,
                pod_name=data.pod_name,
                container_names=required_containers,
                timeout_seconds=CONTAINER_READINESS_TIMEOUT_SECONDS
            )

            # save the pod
            return {**SaveUtility.save_image(data), 'pod_name': data.pod_name, 'namespace_name': data.namespace_name}
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
        '''
        Create a pod.
        :params: data: CreatePodDataClass
        :returns: dict: Pod Details
        '''
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
            # Build resource requirements from the request's ResourceRequirementsDataClass
            rr: ResourceRequirementsDataClass | None = data.resource_requirements
            requests: dict = {}
            limits: dict = {}
            if rr:
                rr_dict: dict = rr.to_dict()
                # Map dataclass fields to Kubernetes resource keys and bucket (requests/limits)
                field_mapping: dict[str, tuple[str, str]] = {
                    "cpu_request": ("requests", "cpu"),
                    "cpu_limit": ("limits", "cpu"),
                    "memory_request": ("requests", "memory"),
                    "memory_limit": ("limits", "memory"),
                    "ephemeral_request": ("requests", "ephemeral-storage"),
                    "ephemeral_limit": ("limits", "ephemeral-storage"),
                }
                for field_name, (bucket, k8s_key) in field_mapping.items():
                    value = rr_dict.get(field_name)
                    if not value:
                        continue
                    if bucket == "requests":
                        requests[k8s_key] = value
                    else:
                        limits[k8s_key] = value

            resource_requirements_k8s: V1ResourceRequirements | None = None
            if requests or limits:
                resource_requirements_k8s = V1ResourceRequirements(
                    requests=requests or None,
                    limits=limits or None,
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
                    volume_mounts=[snapshot_volume_mount],
                    resources=resource_requirements_k8s or None,
                ),
                V1Container(
                    name=SNAPSHOT_SIDECAR_NAME,
                    image=SNAPSHOT_SIDECAR_IMAGE_NAME,
                    security_context=V1SecurityContext(
                        privileged=True
                    ),
                    volume_mounts=[snapshot_volume_mount],
                    resources=resource_requirements_k8s or None,
                ),
                V1Container(
                    name=STATUS_SIDECAR_NAME,
                    image=STATUS_SIDECAR_IMAGE_NAME,
                    security_context=V1SecurityContext(
                        privileged=True
                    ),
                    env=environment_variables,
                    resources=resource_requirements_k8s or None,
                )
            ]
            # Create volumes for the pod, with optional snapshot size limit
            empty_dir_kwargs: dict = {}
            if rr and rr.snapshot_size_limit:
                empty_dir_kwargs["size_limit"] = rr.snapshot_size_limit
            volumes = [
                V1Volume(
                    name="snapshot-volume",
                    empty_dir=V1EmptyDirVolumeSource(**empty_dir_kwargs),
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
        '''
        Poll pod termination.
        :params: namespace_name: str
        :params: pod_name: str
        :params: timeout_seconds: float
        '''
        is_terminated: bool = False
        while is_terminated != True:
            pod: dict = cls.get(GetPodDataClass(**{'namespace_name': namespace_name, 'pod_name': pod_name}))
            is_terminated = (pod == {})
            print(f'Pod: {pod_name} Deleted:', is_terminated)
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeletePodDataClass) -> dict:
        '''
        Delete a pod.
        :params: data: DeletePodDataClass
        :returns: dict: Status
        '''
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
