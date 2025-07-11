1. Persist container data. Right now, if the pod goes down, the data is lost.
2. Add websocket testing.


# Volumes
1. Add an option in CreatePodDataclass. persist_container_data boolean. Default value is False
2. Add this same option to CreateContainerDataClass.

# Ingress option
1. Add a flag expose_container boolean. Default value is False. This is for ingress. - Dont do this until business requirement comes up.

# Issue
1. Ingress has no port, fix that. Decide how to get the port.


# Security

## Potential Security Concerns

### Ingress Exposure

Your Server (SSR UI) is the only one with an Ingress, which is good since it reduces external exposure.
Question: Is WebSocket traffic being proxied through this Ingress? If so, ensure it's using TLS (wss://) to avoid MITM attacks.

### WebSocket Service Exposure
If the WebSocket Pod is communicating directly with the SSR UI server, it should not be publicly accessible.
Use NetworkPolicies to restrict access to the WebSocket Pod so that only the SSR UI server can connect.

### SSH Container Risks
An SSH Container inside your cluster is a high-security risk unless properly locked down.
Questions to consider:
1. Who has access to this SSH container?
2. Does it allow root access?
3. Are SSH keys stored securely (e.g., in Kubernetes Secrets)?
4. Can you limit access to specific namespaces or IP ranges?

### Container Maker (gRPC) Security
Since this service creates WebSocket and SSH pods, it has significant privileges.
Make sure:
It runs with the least privilege necessary.
Authentication and authorization checks are in place for gRPC requests.
It cannot be called externally (use ClusterIP instead of LoadBalancer or NodePort).

### Recommendations
✔ Ingress Best Practices
---
Ensure TLS termination (HTTPS/WSS) at the ingress level.
Use ingress.allowlist annotations (if using Nginx) to restrict access to trusted sources.

✔ Network Security
---
Apply NetworkPolicies to ensure only allowed components can communicate.
Example:
```yaml
kind: NetworkPolicy
apiVersion: networking.k8s.io/v1
metadata:
  name: restrict-websocket
  namespace: your-namespace
spec:
  podSelector:
    matchLabels:
      app: websocket
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: server
```

### Limit SSH Risks

Avoid running SSH inside Kubernetes unless absolutely necessary.
If needed:
Use ephemeral SSH access (e.g., remove access when not in use).
Restrict IPs that can connect using NetworkPolicy or security groups.

✔ Container Maker Security
---
Use RBAC to limit the permissions of the gRPC service.
Validate requests strictly to prevent unauthorized container creation.
Would you like a deeper dive into securing SSH inside Kubernetes? 🚀


# Other fixes
1. The pod is returning even when there is an image pullback error.


# TO TEST:
1. Test with empty environment variables.


# TODO:
1. Add NFS volume and persistence test.
2. Propagate errors properly.
3. Add deployment scripts for production deployment.
4. Add image import.
5. Add image export.

# TODO NOW:
1. Remove volume manager and all of its associates.
    - Don't check for associated volumes when deleting pods.
    - Don't check for volume config while creating pods.
    - Check all areas that volumes effect and remove those.

2. Add emptyDir volume to the created pods.
3. Add a privileged sidecar with docker running in it.