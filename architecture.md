# Container Maker Architecture

## Overview

Container Maker is a Kubernetes-native microservice that provides a high-level abstraction for managing containers (pods, services, and ingresses) through a gRPC API. It simplifies container lifecycle management by handling resource creation, deletion, and cascading relationships automatically.

## System Architecture

```mermaid
graph TB
    Client[gRPC Client] -->|gRPC Request| Server[gRPC Server<br/>app.py]
    Server -->|Transform| Servicer[ContainerMakerAPIServicerImpl<br/>servicer.py]
    Servicer -->|Transform| Transformer[Data Transformers<br/>grpc/data_transformer/]
    Transformer -->|Dataclass| ContainerMgr[Container Manager<br/>containers.py]
    ContainerMgr -->|Dataclass| ResourceMgr[Resource Managers<br/>resources/]
    ResourceMgr -->|Kubernetes API| K8sAPI[Kubernetes API<br/>CoreV1Api]
    K8sAPI -->|Resources| K8sCluster[Kubernetes Cluster]
    
    style Client fill:#e1f5ff
    style Server fill:#fff4e1
    style Servicer fill:#fff4e1
    style Transformer fill:#f3e5f5
    style ContainerMgr fill:#e8f5e9
    style ResourceMgr fill:#e8f5e9
    style K8sAPI fill:#ffebee
    style K8sCluster fill:#ffebee
```

## Layered Architecture

```mermaid
graph LR
    subgraph "API Layer"
        A1[gRPC Server]
        A2[Servicer Implementation]
    end
    
    subgraph "Transformation Layer"
        T1[Input Transformers<br/>Protobuf → Dataclass]
        T2[Output Transformers<br/>Dict → Protobuf]
    end
    
    subgraph "Business Logic Layer"
        C1[Container Manager<br/>High-level abstraction]
        C2[Container Helper<br/>Utility methods]
    end
    
    subgraph "Resource Management Layer"
        R1[Pod Manager]
        R2[Service Manager]
        R3[Ingress Manager]
        R4[Namespace Manager]
    end
    
    subgraph "Infrastructure Layer"
        I1[Kubernetes Client]
        I2[Kubernetes Cluster]
    end
    
    A1 --> A2
    A2 --> T1
    T1 --> C1
    C1 --> C2
    C2 --> R1
    C2 --> R2
    C2 --> R3
    C2 --> R4
    R1 --> I1
    R2 --> I1
    R3 --> I1
    R4 --> I1
    I1 --> I2
    
    style A1 fill:#fff4e1
    style A2 fill:#fff4e1
    style T1 fill:#f3e5f5
    style T2 fill:#f3e5f5
    style C1 fill:#e8f5e9
    style C2 fill:#e8f5e9
    style R1 fill:#e1f5ff
    style R2 fill:#e1f5ff
    style R3 fill:#e1f5ff
    style R4 fill:#e1f5ff
    style I1 fill:#ffebee
    style I2 fill:#ffebee
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant gRPCServer
    participant Servicer
    participant InputTransformer
    participant ContainerManager
    participant ResourceManager
    participant KubernetesAPI
    participant OutputTransformer
    
    Client->>gRPCServer: CreateContainerRequest
    gRPCServer->>Servicer: createContainer()
    Servicer->>InputTransformer: transform(request)
    InputTransformer->>ContainerManager: CreateContainerDataClass
    ContainerManager->>ResourceManager: CreatePodDataClass
    ResourceManager->>KubernetesAPI: create_namespaced_pod()
    KubernetesAPI-->>ResourceManager: V1Pod
    ResourceManager-->>ContainerManager: dict (pod response)
    
    alt Exposure Level > INTERNAL
        ContainerManager->>ResourceManager: CreateServiceDataClass
        ResourceManager->>KubernetesAPI: create_namespaced_service()
        KubernetesAPI-->>ResourceManager: V1Service
        ResourceManager-->>ContainerManager: dict (service response)
    end
    
    alt Exposure Level > CLUSTER_EXTERNAL
        ContainerManager->>ResourceManager: CreateIngressDataClass
        ResourceManager->>KubernetesAPI: create_namespaced_ingress()
        KubernetesAPI-->>ResourceManager: V1Ingress
        ResourceManager-->>ContainerManager: dict (ingress response)
    end
    
    ContainerManager-->>Servicer: dict (container response)
    Servicer->>OutputTransformer: transform(container)
    OutputTransformer-->>Servicer: ContainerResponse
    Servicer-->>gRPCServer: ContainerResponse
    gRPCServer-->>Client: ContainerResponse
```

## Component Relationships

```mermaid
classDiagram
    class ContainerMakerAPIServicerImpl {
        +createContainer()
        +listContainer()
        +getContainer()
        +deleteContainer()
        +saveContainer()
    }
    
    class KubernetesContainerManager {
        +create()
        +list()
        +get()
        +delete()
        +save()
    }
    
    class KubernetesContainerHelper {
        +check_pod()
        +check_service()
        +check_ingress()
        +delete_pod()
        +delete_service()
        +delete_ingress()
        +delete_lingering_namespaces()
    }
    
    class PodManager {
        +create()
        +list()
        +get()
        +delete()
        +save()
        +get_pod_containers()
        +get_pod_response()
    }
    
    class ServiceManager {
        +create()
        +list()
        +get()
        +delete()
        +get_service_response()
        +get_associated_pods()
    }
    
    class IngressManager {
        +create()
        +list()
        +get()
        +delete()
        +get_ingress_response()
        +get_associated_services()
    }
    
    class NamespaceManager {
        +create()
        +list()
        +get()
        +delete()
    }
    
    ContainerMakerAPIServicerImpl --> KubernetesContainerManager
    KubernetesContainerManager --> KubernetesContainerHelper
    KubernetesContainerManager --> PodManager
    KubernetesContainerManager --> ServiceManager
    KubernetesContainerManager --> IngressManager
    KubernetesContainerManager --> NamespaceManager
    KubernetesContainerHelper --> PodManager
    KubernetesContainerHelper --> ServiceManager
    KubernetesContainerHelper --> IngressManager
    KubernetesContainerHelper --> NamespaceManager
    ServiceManager --> PodManager
    IngressManager --> ServiceManager
```

## Resource Hierarchy

```mermaid
graph TD
    Container[Container<br/>High-level abstraction] -->|INTERNAL| Pod[Pod<br/>Main Container + Sidecars]
    Container -->|CLUSTER_LOCAL| Service[Service<br/>ClusterIP]
    Container -->|CLUSTER_EXTERNAL| ServiceLB[Service<br/>LoadBalancer]
    Container -->|EXPOSED| Ingress[Ingress<br/>External Access]
    
    Pod -->|Contains| MainContainer[Main Container]
    Pod -->|Contains| SnapshotSidecar[Snapshot Sidecar]
    Pod -->|Contains| StatusSidecar[Status Sidecar]
    
    Service -->|Selects| Pod
    ServiceLB -->|Selects| Pod
    Ingress -->|Routes to| ServiceLB
    Ingress -->|Routes to| Service
    
    Pod -->|Mounted| EmptyDir[EmptyDir Volume<br/>Snapshot Storage]
    
    style Container fill:#e8f5e9
    style Pod fill:#e1f5ff
    style Service fill:#fff4e1
    style ServiceLB fill:#fff4e1
    style Ingress fill:#f3e5f5
    style MainContainer fill:#ffebee
    style SnapshotSidecar fill:#ffebee
    style StatusSidecar fill:#ffebee
    style EmptyDir fill:#f5f5f5
```

## Container Creation Flow

```mermaid
flowchart TD
    Start[Create Container Request] --> Validate[Validate Publish Information]
    Validate --> CreateNS[Create/Get Namespace]
    CreateNS --> CreatePod[Create Pod<br/>with Resource Requirements]
    CreatePod --> CheckExposure{Exposure Level?}
    
    CheckExposure -->|INTERNAL| ReturnPod[Return Pod Container]
    CheckExposure -->|CLUSTER_LOCAL| CreateSvcIP[Create ClusterIP Service]
    CheckExposure -->|CLUSTER_EXTERNAL| CreateSvcLB[Create LoadBalancer Service]
    CheckExposure -->|EXPOSED| CreateSvcLB
    
    CreateSvcIP --> ReturnSvc[Return Service Container]
    CreateSvcLB --> CheckIngress{Exposure Level<br/>EXPOSED?}
    CheckIngress -->|Yes| CreateIng[Create Ingress]
    CheckIngress -->|No| ReturnSvc
    CreateIng --> ReturnIng[Return Ingress Container]
    
    ReturnPod --> End[Container Response]
    ReturnSvc --> End
    ReturnIng --> End
    
    style Start fill:#e8f5e9
    style CreatePod fill:#e1f5ff
    style CreateSvcIP fill:#fff4e1
    style CreateSvcLB fill:#fff4e1
    style CreateIng fill:#f3e5f5
    style End fill:#e8f5e9
```

## Container Deletion Flow

```mermaid
flowchart TD
    Start[Delete Container Request] --> FindResource{Find Resource Type}
    
    FindResource -->|Pod| DeletePod[Delete Pod]
    FindResource -->|Service| GetSvc[Get Service]
    FindResource -->|Ingress| GetIng[Get Ingress]
    
    GetSvc --> GetPods[Get Associated Pods<br/>from associated_resources]
    GetPods --> DeletePods[Delete All Associated Pods]
    DeletePods --> DeleteSvc[Delete Service]
    
    GetIng --> GetSvcs[Get Associated Services<br/>from associated_resources]
    GetSvcs --> DeleteSvcs[Delete All Associated Services]
    DeleteSvcs --> DeleteIng[Delete Ingress]
    
    DeletePod --> Cleanup[Delete Lingering Resources]
    DeleteSvc --> Cleanup
    DeleteIng --> Cleanup
    
    Cleanup --> CheckNS{Namespace Empty?}
    CheckNS -->|Yes| DeleteNS[Delete Namespace]
    CheckNS -->|No| End[Return Success]
    DeleteNS --> End
    
    style Start fill:#e8f5e9
    style DeletePod fill:#ffebee
    style DeleteSvc fill:#ffebee
    style DeleteIng fill:#ffebee
    style Cleanup fill:#fff4e1
    style End fill:#e8f5e9
```

## Data Structures

### Container Response Format

```python
{
    'container_type': 'pod' | 'service' | 'ingress',
    'container_id': str,  # UUID from Kubernetes resource
    'container_name': str,
    'container_ip': str,
    'container_network': str,  # Namespace name
    'container_ports': list[dict],
    'container_resources': dict,  # Only in create response
    'container_associated_resources': dict  # Nested resource hierarchy
}
```

### Associated Resources Structure

```python
# For Pod:
container_associated_resources = {}  # Empty, pods have no dependencies

# For Service:
container_associated_resources = {
    'pods': [
        {
            'resource_type': 'pod',
            'pod_id': str,
            'pod_name': str,
            'associated_resources': [
                {
                    'resource_type': 'pod_container',
                    'container_name': str,
                    'container_resources': dict
                }
            ]
        }
    ]
}

# For Ingress:
container_associated_resources = {
    'services': [
        {
            'resource_type': 'service',
            'service_id': str,
            'service_name': str,
            'associated_resources': [
                {
                    'resource_type': 'pod',
                    'pod_id': str,
                    'pod_name': str,
                    'associated_resources': [...]
                }
            ]
        }
    ]
}
```

## Pod Structure

Each pod created by Container Maker contains three containers:

1. **Main Container**: User's application container
2. **Snapshot Sidecar**: Handles filesystem snapshots for save operations
3. **Status Sidecar**: Monitors and reports container status

All containers share:
- Resource limits (CPU, memory, ephemeral storage)
- Security context (privileged mode)
- Volume mounts (snapshot volume for main + snapshot sidecar)

## Resource Requirements

Default resource limits applied to all containers:

- **CPU**: Request `100m`, Limit `1`
- **Memory**: Request `256Mi`, Limit `1Gi`
- **Ephemeral Storage**: Request `512Mi`, Limit `1Gi`
- **Snapshot Volume**: Size limit `2Gi` (EmptyDir)

## Key Design Decisions

1. **Layered Abstraction**: Container Manager provides a high-level API that abstracts away Kubernetes complexity
2. **Cascading Deletes**: Deleting a container automatically deletes all associated resources
3. **Exposure Levels**: Four levels (INTERNAL, CLUSTER_LOCAL, CLUSTER_EXTERNAL, EXPOSED) determine which resources are created
4. **Unified Response Format**: All resources return consistent response structures with `resource_type` and `associated_resources`
5. **Resource Deduplication**: List operation excludes nested resources (pods in services, services in ingresses)
6. **Automatic Namespace Management**: Namespaces are created automatically and cleaned up when empty

## Error Handling

Errors are propagated through layers:
- Kubernetes API errors → `ApiException`
- Timeout errors → `TimeoutError`
- Runtime environment mismatches → `UnsupportedRuntimeEnvironment`
- All errors are wrapped with context and re-raised

## Testing Strategy

- **Unit Tests**: Data transformers (Protobuf ↔ Dataclass)
- **Integration Tests**: Resource managers (Pod, Service, Ingress)
- **Integration Tests**: Container manager (Create, List, Get, Delete, Save)
- **Integration Tests**: gRPC servicer (end-to-end API tests)

Tests use real Kubernetes clusters and clean up resources automatically.

