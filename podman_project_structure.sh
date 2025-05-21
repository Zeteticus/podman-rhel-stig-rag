#!/bin/bash
# Create directory structure for podman-rhel-stig-rag project

# Create main directories
mkdir -p podman-rhel-stig-rag/{config,systemd/{quadlet},docs,app}

# Copy core files
cp Containerfile-fixed podman-rhel-stig-rag/Containerfile
cp deploy-podman-fixed.sh podman-rhel-stig-rag/deploy-podman.sh
cp cgroups-troubleshooting.md podman-rhel-stig-rag/docs/

# Create additional files
touch podman-rhel-stig-rag/manage-stig-rag.sh
touch podman-rhel-stig-rag/config/config.env.template
touch podman-rhel-stig-rag/config/container-policy.json
touch podman-rhel-stig-rag/systemd/stig-rag-pod.service
touch podman-rhel-stig-rag/systemd/quadlet/stig-rag.container
touch podman-rhel-stig-rag/docs/podman-security.md
touch podman-rhel-stig-rag/docs/rhel-optimization.md
touch podman-rhel-stig-rag/LICENSE

# Fix permissions
chmod +x podman-rhel-stig-rag/deploy-podman.sh

# Create placeholder for application code
echo "# Application code placeholder
# Copy actual RHEL STIG RAG application files here from the main project" > podman-rhel-stig-rag/app/README.md

echo "Podman project structure created successfully!"
echo "Directory: podman-rhel-stig-rag/"
