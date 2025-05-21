# RHEL-Specific Optimizations for Podman Deployment

This document outlines specific optimizations for deploying the RHEL STIG RAG system on Red Hat Enterprise Linux using Podman containers.

## RHEL Version Considerations

### RHEL 9 Optimizations

RHEL 9 introduced several features and improvements for container deployments:

#### Cgroups v2

RHEL 9 uses cgroups v2 by default, which offers improved resource control:

```bash
# Check if using cgroups v2
test -d /sys/fs/cgroup/cgroup.controllers && echo "Using cgroups v2" || echo "Using cgroups v1"
```

**Optimization for cgroups v2:**
```bash
# Ensure proper cgroups v2 delegation
echo 'DefaultDelegation=yes' | sudo tee -a /etc/systemd/system.conf
sudo systemctl daemon-reload
```

#### Quadlet Integration

RHEL 9 includes systemd 250+ which supports Quadlet for improved container integration:

```bash
# Create quadlet directory
mkdir -p ~/.config/containers/systemd

# Use quadlet container definition
cp systemd/quadlet/stig-rag.container ~/.config/containers/systemd/

# Reload systemd
systemctl --user daemon-reload
```

#### Improved UBI Base Images

Take advantage of the latest UBI 9 images which are more optimized:

```dockerfile
# In Containerfile
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest
```

### RHEL 8 Considerations

For RHEL 8 deployments, some adaptations may be necessary:

#### Cgroups v1

RHEL 8 typically uses cgroups v1, which requires different handling:

```bash
# For RHEL 8, use cgroupfs manager
./deploy-podman.sh --cgroup-manager=cgroupfs deploy
```

#### Container Tools

Ensure you're using the latest container tools:

```bash
# Install latest container tools
sudo dnf module install -y container-tools:latest
```

## Performance Optimizations

### CPU Performance

CPU optimizations for RHEL platforms:

```bash
# Use performance governor
sudo tuned-adm profile throughput-performance

# Configure CPU affinity for container
./deploy-podman.sh --cpuset-cpus=0-3 deploy
```

### Memory Management

Optimize memory usage on RHEL systems:

```bash
# Disable transparent hugepages for consistent performance
echo never | sudo tee /sys/kernel/mm/transparent_hugepage/enabled

# Set container memory limits
./deploy-podman.sh --memory=4g --memory-swap=6g deploy
```

### Storage Optimizations

Container storage optimizations for RHEL:

```bash
# Use overlay2 storage driver
sudo mkdir -p /etc/containers
cat << EOF | sudo tee /etc/containers/storage.conf
[storage]
driver = "overlay2"
runroot = "/var/run/containers/storage"
graphroot = "/var/lib/containers/storage"

[storage.options]
size = "20G"
EOF
```

### Network Performance

RHEL-specific network tuning:

```bash
# Enable slirp4netns port forwarding
mkdir -p ~/.config/containers
cat << EOF > ~/.config/containers/containers.conf
[engine]
network_cmd_options = ["port_handler=slirp4netns"]
EOF

# For high-performance applications
./deploy-podman.sh --network=host deploy  # Note: reduces isolation
```

## Integration with RHEL Services

### RHEL System Monitoring

Integrate with RHEL monitoring tools:

```bash
# Install Performance Co-Pilot
sudo dnf install -y pcp-zeroconf

# Configure container metrics collection
sudo systemctl enable --now pmcd pmlogger
```

### RHEL Subscription Manager

For properly subscribed RHEL systems:

```bash
# Mount subscription manager certificates for container access to repos
./deploy-podman.sh \
  --volume /etc/pki/entitlement:/etc/pki/entitlement:ro \
  --volume /etc/rhsm:/etc/rhsm:ro \
  deploy
```

### SELinux Optimization

Optimize SELinux for container workloads:

```bash
# Install container SELinux policy
sudo dnf install -y container-selinux

# Create custom policy for STIG RAG
sudo semodule -i stig-rag.pp  # Created with audit2allow
```

## Podman Configuration for RHEL

### Podman Settings

Optimize podman configuration for RHEL:

```bash
# Create optimized configuration
mkdir -p ~/.config/containers
cat << EOF > ~/.config/containers/containers.conf
[engine]
runtime = "crun"
image_default_transport = "docker://"
cgroup_manager = "systemd"
events_logger = "journald"
log_level = "info"

[engine.runtimes]
crun = [
  "/usr/bin/crun"
]

[containers]
netns = "bridge"
userns = "auto"
ipcns = "shareable"
utsns = "private"

[network]
network_backend = "cni"
EOF
```

### Registry Configuration

Configure container registries for RHEL:

```bash
# Create optimized registries configuration
cat << EOF > ~/.config/containers/registries.conf
# Registries configuration
unqualified-search-registries = ["registry.access.redhat.com", "docker.io"]

[[registry]]
prefix = "registry.access.redhat.com"
location = "registry.access.redhat.com"
insecure = false

[[registry]]
prefix = "docker.io"
location = "docker.io"
insecure = false
EOF
```

## SystemTap/BPF Analysis

For advanced performance analysis on RHEL:

```bash
# Install tools
sudo dnf install -y bpftrace systemtap

# Analyze container I/O performance
sudo bpftrace -e 'tracepoint:syscalls:sys_enter_read /comm == "python3"/ { @bytes = hist(args->count); }'
```

## Recommended RHEL Settings

### System Settings

Recommended system settings for container hosts:

```bash
# Set system limits for containers
cat << EOF | sudo tee /etc/sysctl.d/99-containers.conf
# Maximum number of open files
fs.file-max = 1000000

# Maximum number of processes
kernel.pid_max = 1000000

# Allow unprivileged users to use user namespaces (needed for rootless)
kernel.unprivileged_userns_clone = 1

# Increase netfilter connection tracking
net.netfilter.nf_conntrack_max = 1000000

# Increase memory mapped areas
vm.max_map_count = 262144
EOF

# Apply settings
sudo sysctl --system
```

### User Settings

For optimized rootless deployments:

```bash
# Enable lingering for user session
loginctl enable-linger $USER

# Set user limits
mkdir -p ~/.config/systemd/user.conf.d/
cat << EOF > ~/.config/systemd/user.conf.d/limits.conf
[Manager]
DefaultLimitNOFILE=1048576
DefaultLimitNPROC=65536
EOF
```

## RHEL-Specific Tuning Profiles

Use RHEL's tuned profiles for optimal performance:

```bash
# List available profiles
sudo tuned-adm list

# For container hosts
sudo tuned-adm profile virtual-host

# Verify applied profile
sudo tuned-adm active
```

## Kernel Module Configuration

Ensure proper kernel modules for containers:

```bash
# Check required modules
for mod in overlay br_netfilter ip_tables iptable_nat iptable_filter iptable_mangle; do
  lsmod | grep -q "$mod" || echo "$mod not loaded"
done

# Load required modules
sudo modprobe overlay
sudo modprobe br_netfilter
```

## References

- [Red Hat Container Performance Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/index)
- [RHEL 9 Tuning Guide](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/monitoring_and_managing_system_status_and_performance/getting-started-with-tuned_monitoring-and-managing-system-status-and-performance)
- [Podman Performance Best Practices](https://developers.redhat.com/blog/2021/04/30/container-performance-analysis-at-rhel-container-tools)
- [Performance Tuning for Containers](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/managing_monitoring_and_updating_the_kernel/analyzing-system-performance-with-bpf-compiler-collection_managing-monitoring-and-updating-the-kernel)