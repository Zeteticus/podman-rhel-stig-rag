# Podman Security Guide for RHEL STIG RAG

This document outlines the security measures implemented in the Podman deployment of the RHEL STIG RAG system and provides guidance on security best practices.

## Security Features

### Rootless Containers

By default, this deployment uses rootless containers, providing significant security benefits:

- **User namespace isolation**: Container processes run as unprivileged users
- **No privileged daemon**: Unlike Docker, no root daemon is required
- **Reduced attack surface**: Even if container is compromised, attacker has limited privileges
- **Lower risk**: Minimized impact if vulnerabilities are discovered

### Red Hat Universal Base Image (UBI)

Our Containerfile uses the official Red Hat UBI image which provides:

- **Regularly updated**: Security patches applied promptly
- **RHEL compatibility**: Native compatibility with Red Hat environments
- **Reduced footprint**: Minimal attack surface
- **Enterprise support**: Backed by Red Hat's security team

### SELinux Integration

SELinux provides mandatory access controls for enhanced security:

- **Volume labeling**: `:Z` suffix ensures proper SELinux context
- **Process confinement**: Processes limited to defined contexts
- **Fine-grained access control**: Beyond standard Linux permissions

### Reduced Capabilities

The container drops all capabilities by default and only adds those specifically required:

```dockerfile
# Drop all capabilities
--cap-drop=ALL
```

### Non-root User

The container runs as a non-root user:

```dockerfile
# Create non-root user
RUN useradd -r -u 1001 -g 0 -m -d /app -s /bin/bash stigrag
USER stigrag
```

### Read-only Root Filesystem

For enhanced security, you can enable a read-only root filesystem:

```bash
# Enable in deploy-podman.sh
--read-only \
```

## Security Best Practices

### 1. Secrets Management

**Never** hard-code sensitive information. Instead:

```bash
# Environment variables (preferred for development)
./deploy-podman.sh --env-file /path/to/secure/env deploy

# Podman secrets (preferred for production)
podman secret create stig-api-key /path/to/api_key.txt
podman run --secret stig-api-key ...
```

### 2. Network Security

Limit network exposure:

```bash
# Bind to localhost only for internal use
./deploy-podman.sh --port 127.0.0.1:8000:8000 deploy

# Use network isolation
./deploy-podman.sh --network isolated deploy
```

### 3. Resource Limits

Prevent denial-of-service scenarios:

```bash
./deploy-podman.sh --memory 4g --cpus 2 deploy
```

### 4. Regular Updates

Keep container images updated:

```bash
# Update container with latest security patches
./manage-stig-rag.sh update
```

### 5. Scan for Vulnerabilities

Regularly scan your containers:

```bash
# Install podman-compose if needed
sudo dnf install podman-compose

# Scan image for vulnerabilities
podman scan $IMAGE_NAME
```

## SELinux Configuration

### Troubleshooting SELinux Denials

If you encounter SELinux denials:

```bash
# Check for SELinux denials
sudo ausearch -m avc -ts recent

# Generate policy module for denials
sudo audit2allow -a -M stig-rag-policy

# Apply the policy
sudo semodule -i stig-rag-policy.pp
```

### Working with SELinux and Volumes

Proper volume labeling is critical:

```bash
# The :Z suffix relabels with a private unshared label
--volume /path/on/host:/container/path:Z

# The :z suffix relabels with a shared label
--volume /path/on/host:/container/path:z
```

## Firewall Configuration

Restrict access with firewalld:

```bash
# Open specific port for STIG RAG service
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload

# Or create a dedicated service
sudo firewall-cmd --permanent --new-service=stig-rag
sudo firewall-cmd --permanent --service=stig-rag --add-port=8000/tcp
sudo firewall-cmd --permanent --add-service=stig-rag
sudo firewall-cmd --reload
```

## Audit Logging

Enable audit logging for container activities:

```bash
# Enable audit logging in container
./deploy-podman.sh --log-driver=journald deploy

# View audit logs
sudo journalctl -t podman
```

## Hardening Checklist

- [ ] Run with rootless mode
- [ ] Apply resource limits
- [ ] Use SELinux
- [ ] Configure firewall rules
- [ ] Enable audit logging
- [ ] Drop unnecessary capabilities
- [ ] Use secrets management for sensitive data
- [ ] Implement read-only filesystem where possible
- [ ] Scan images regularly for vulnerabilities
- [ ] Keep base images updated

## Compliance with Security Standards

This deployment is designed with several security frameworks in mind:

- **NIST SP 800-53**: Controls for federal information systems
- **CIS Benchmarks**: Best practices for secure configuration
- **Red Hat Enterprise Linux Security Guide**: Official Red Hat security guidance
- **DISA STIG**: Security Technical Implementation Guides from the Defense Information Systems Agency

## References

- [Podman Security](https://docs.podman.io/en/latest/markdown/podman.1.html#security)
- [RHEL Security Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/security_hardening/index)
- [SELinux User's and Administrator's Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/using_selinux/index)
- [Container Security Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/building_running_and_managing_containers/assembly_container-security_building-running-and-managing-containers)
