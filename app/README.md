# podman-rhel-stig-rag
Podman deployment for RHEL STIG RAG system

This is a complete, focused Podman deployment project for the RHEL STIG RAG system. This separate project allows you to concentrate solely on the containerization and deployment aspects without getting distracted by the core application code.
What's Included in the Podman Project:
1. Project Structure
I've provided a script that creates the following directory structure:
podman-rhel-stig-rag/
├── Containerfile               # Container definition with cgroups fixes
├── deploy-podman.sh            # Deployment script with enhanced options
├── manage-stig-rag.sh          # Management utility script
├── config/                     # Configuration templates
├── systemd/                    # Systemd integration files
│   └── quadlet/                # For RHEL 9 systemd 250+
└── docs/                       # Documentation
2. Core Deployment Files

Containerfile: Optimized for RHEL with cgroups compatibility
deploy-podman.sh: Full-featured deployment script with cgroups fixes
manage-stig-rag.sh: Comprehensive management utility

3. Configuration Files

config.env.template: Environment variables for customization
container-policy.json: Container security policy

4. Documentation

podman-security.md: Security best practices
rhel-optimization.md: RHEL-specific tuning
cgroups-troubleshooting.md: Solutions for cgroups issues
setup-instructions.md: Step-by-step installation guide

5. Systemd Integration

systemd service files: For automatic startup
quadlet definitions: For RHEL 9's modern container management

Key Features of This Podman Project:

Cgroups Issue Fixed: Solutions for the cgroups problems you mentioned
RHEL Optimized: Specifically designed for Red Hat environments
Rootless Security: Enhanced security through user namespaces
Easy Management: Simple commands for day-to-day operations
Comprehensive Documentation: Detailed guides for all aspects

Getting Started:
To use this project, you would:

Create a new repository for just the Podman deployment:
bashgit init podman-rhel-stig-rag
cd podman-rhel-stig-rag

Copy these files into the repository structure
Deploy with cgroups fixes enabled:
bash./deploy-podman.sh --skip-cgroups deploy


This separate project gives you a clean, focused approach to containerization, making it easier to experiment with deployment options without affecting the core application code. You can link to it from your main RHEL STIG RAG repository as the recommended deployment method.
