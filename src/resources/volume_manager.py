# modules
import time
from src.resources import KubernetesResourceManager
from src.resources.dataclasses.volume.create_volume_dataclass import CreateVolumeDataClass
from src.resources.dataclasses.volume.delete_volume_dataclass import DeleteVolumeDataClass
from src.resources.dataclasses.volume.get_volume_dataclass import GetVolumeDataClass
from src.resources.dataclasses.volume.list_volume_dataclass import ListVolumeDataClass

# common
from src.common.exceptions import UnsupportedRuntimeEnvironment

# kubernetes
from kubernetes.client import ApiException
from kubernetes.client.models import V1PersistentVolume, V1PersistentVolumeClaim


class VolumeManager(KubernetesResourceManager):
    '''
    Manage kubernetes volumes.
    '''

    @classmethod
    def list(cls, data: ListVolumeDataClass) -> list[dict]:
        '''
        List volumes.
        '''
        try:
            cls.check_kubernetes_client()
            volumes: list[V1PersistentVolume] = cls.client.list_persistent_volume().items
            volume_list: list[dict] = []
            for volume in volumes:
                volume_dict: dict = {
                    'volume': {
                        'volume_id': volume.metadata.uid,
                        'volume_name': volume.metadata.name,
                        'volume_size': volume.spec.capacity['storage'],
                        'volume_access_modes': volume.spec.access_modes,
                        'volume_reclaim_policy': volume.spec.persistent_volume_reclaim_policy,
                        'volume_nfs_server': volume.spec.nfs.server,
                        'volume_nfs_path': volume.spec.nfs.path,
                    } if volume.metadata.name else {},
                }
                claim: V1PersistentVolumeClaim = cls.client.read_namespaced_persistent_volume_claim(
                    name=f'{volume.metadata.name}-claim', namespace=data.namespace_name)
                if claim:
                    volume_dict['claim'] = {
                        'claim_id': claim.metadata.uid,
                        'claim_name': claim.metadata.name,
                        'claim_namespace': claim.metadata.namespace,
                    } if claim.metadata.name else {}
                volume_list.append(volume_dict)
            return volume_list
        except ApiException as ae:
            raise ApiException(f'Error occured while listing volumes: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Run time Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unkown error occured: {str(e)}') from e

    @classmethod
    def get(cls, data: GetVolumeDataClass) -> dict:
        '''
        Get a volume and claim associated with it.
        '''
        try:
            cls.check_kubernetes_client()
            # PV is cluster-wide, not namespaced
            try:
                pv_response: V1PersistentVolume | None = cls.client.read_persistent_volume(name=data.volume_name)
            except ApiException:
                pv_response: V1PersistentVolume | None = None
            # PVC is namespaced
            try:
                pvc_response: V1PersistentVolumeClaim | None = cls.client.read_namespaced_persistent_volume_claim(
                    name=f'{data.volume_name}-claim',
                    namespace=data.namespace_name
                )
            except ApiException:
                pvc_response: V1PersistentVolumeClaim | None = None

            return {
                'volume': {
                    'volume_id': pv_response.metadata.uid,
                    'volume_name': pv_response.metadata.name,
                    'volume_size': pv_response.spec.capacity['storage'],
                    'volume_access_modes': pv_response.spec.access_modes,
                    'volume_reclaim_policy': pv_response.spec.persistent_volume_reclaim_policy,
                    'volume_nfs_server': pv_response.spec.nfs.server,
                    'volume_nfs_path': pv_response.spec.nfs.path,
                } if pv_response else {},
                'claim': {
                    'claim_id': pvc_response.metadata.uid,
                    'claim_name': pvc_response.metadata.name,
                    'claim_namespace': pvc_response.metadata.namespace,
                } if pvc_response else {},
            }
        except ApiException as ae:
            if ae.status == 404:
                return {}
            raise ApiException(f'Error occurred while getting pod: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def create(cls, data: CreateVolumeDataClass) -> dict:
        '''
        Create a persistent volume and its corresponding claim.
        '''
        try:
            cls.check_kubernetes_client()
            v: dict = cls.get(GetVolumeDataClass(namespace_name=data.namespace_name, volume_name=data.volume_name))

            # if both exist then simply return
            if v.get('volume', {}) and v.get('claim', {}):
                return v

            # if volume does not exist then create it
            volume_data: dict = v.get('volume', {})
            if not volume_data:
                volume: V1PersistentVolume = V1PersistentVolume(
                    api_version="v1",
                    kind="PersistentVolume",
                    metadata={
                        "name": data.volume_name,
                    },
                    spec={
                        "capacity": {
                            "storage": data.storage_size
                        },
                        "accessModes": [mode if isinstance(mode, str) else mode.value for mode in data.access_modes],
                        "persistentVolumeReclaimPolicy": data.reclaim_policy.value,
                        "storageClassName": "nfs",
                        "nfs": {
                            "server": data.nfs_server,
                            "path": data.nfs_path
                        }
                    }
                )
                pv_response: V1PersistentVolume = cls.client.create_persistent_volume(body=volume)
                volume_data = {
                    'volume_id': pv_response.metadata.uid,
                    'volume_name': pv_response.metadata.name,
                    'volume_size': pv_response.spec.capacity['storage'],
                    'volume_access_modes': pv_response.spec.access_modes,
                    'volume_reclaim_policy': pv_response.spec.persistent_volume_reclaim_policy,
                    'volume_nfs_server': pv_response.spec.nfs.server,
                    'volume_nfs_path': pv_response.spec.nfs.path,
                }

            # if claim does not exist then create it
            claim_data: dict = v.get('claim', {})
            if not claim_data:
                if volume_data and getattr(volume_data, "spec", {}).get("claim_ref"):
                    raise Exception(f"Volume {data.volume_name} is already bound to a claim. Skipping PVC creation.")
                else:
                    # Create corresponding PVC
                    volume_claim: V1PersistentVolumeClaim = V1PersistentVolumeClaim(
                        api_version="v1",
                        kind="PersistentVolumeClaim",
                        metadata={
                            "name": f'{data.volume_name}-claim',
                            "namespace": data.namespace_name
                        },
                        spec={
                            "accessModes": [mode if isinstance(mode, str) else mode.value for mode in data.access_modes],
                            "resources": {
                                "requests": {
                                    "storage": data.storage_size
                                }
                            },
                            "storageClassName": "nfs",
                            "volumeName": data.volume_name
                        }
                    )

                    pvc_response: V1PersistentVolumeClaim = cls.client.create_namespaced_persistent_volume_claim(
                        namespace=data.namespace_name,
                        body=volume_claim
                    )
                    claim_data = {
                        'claim_id': pvc_response.metadata.uid,
                        'claim_name': pvc_response.metadata.name,
                        'claim_namespace': pvc_response.metadata.namespace,
                    }
            return {
                'volume': volume_data,
                'claim': claim_data,
            }
        except ApiException as ae:
            raise ApiException(f'Error occurred while creating volume: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e

    @classmethod
    def poll_termination(cls, namespace_name: str, volume_name: str, timeout_seconds: float = 2.0) -> None:
        while True:
            v: dict = cls.get(GetVolumeDataClass(namespace_name=namespace_name, volume_name=volume_name))
            volume_exists: bool = v.get('volume') != {}
            claim_exists: bool = v.get('claim') != {}
            print(f'Volume: {volume_name} - Volume exists: {volume_exists}, Claim exists: {claim_exists}')
            if not volume_exists and not claim_exists:
                print(f'Volume: {volume_name} and Claim: {volume_name}-claim - Deleted')
                break
            time.sleep(timeout_seconds)

    @classmethod
    def delete(cls, data: DeleteVolumeDataClass) -> dict:
        '''
        Delete a volume and its claim.
        '''
        try:
            cls.check_kubernetes_client()
            v: dict = cls.get(GetVolumeDataClass(namespace_name=data.namespace_name, volume_name=data.volume_name))

            # Delete PVC first if it exists
            if v.get("claim", {}):
                try:
                    print(f"Deleting PVC: {data.volume_name}-claim")
                    cls.client.delete_namespaced_persistent_volume_claim(
                        name=f'{data.volume_name}-claim',
                        namespace=data.namespace_name
                    )
                    print("PVC deletion initiated")
                except ApiException as e:
                    if e.status == 404:
                        print("PVC already deleted")
                    else:
                        raise e

            # Delete PV if it exists
            if v.get("volume", {}):
                try:
                    print(f"Deleting PV: {data.volume_name}")
                    cls.client.delete_persistent_volume(name=data.volume_name)
                    print("PV deletion initiated")
                except ApiException as e:
                    if e.status == 404:
                        print("PV already deleted")
                    else:
                        raise e

            print("Waiting for deletion to complete...")
            cls.poll_termination(data.namespace_name, data.volume_name)
            return {'status': 'success'}
        except ApiException as ae:
            raise ApiException(f'Error occurred while deleting volume: {str(ae)}') from ae
        except UnsupportedRuntimeEnvironment as ure:
            raise UnsupportedRuntimeEnvironment(f'Unsupported Runtime Environment: {str(ure)}') from ure
        except Exception as e:
            raise Exception(f'Unknown error occurred: {str(e)}') from e
