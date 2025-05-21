# Setup Instructions for Podman RHEL STIG RAG Deployment

This document provides step-by-step instructions for setting up the Podman deployment for the RHEL STIG RAG system.

## Prerequisites

Before starting, ensure you have:

- RHEL 8/9 or compatible distribution (CentOS, Fedora, etc.)
- Podman 3.0+ installed
- At least 4GB of free memory
- 10GB of free disk space
- RHEL STIG RAG application code (separate repository)

## Installation Steps

### 1. Install Podman (if not already installed)

**RHEL/CentOS 8/9**:
```bash
sudo dnf install -y podman podman-docker
```

**Fedora**:
```bash
sudo dnf install -y podman podman-docker
```

**Ubuntu 20.04+**:
```bash
sudo apt-get update
sudo apt-get install -y podman
```

### 2. Clone the Repository

```bash
git clone https://github.com/your-username/podman-rhel-stig-rag.git
cd podman-rhel-stig-rag
```

### 3. Make the Deployment Script Executable

```bash
chmod +x deploy-podman.sh
chmod +x manage-stig-rag.sh
```

### 4. Configure Settings (Optional)

Copy the configuration template:
```bash
mkdir -p ~/stig-rag-config
cp config/config.env.template ~/stig-rag-config/config.env
```

Edit the configuration file to match your environment:
```bash
vi ~/stig-rag-config/config.env
```

### 5. Copy Application Code

You need to copy the RHEL STIG RAG application code from the main repository:

```bash
# Assuming the main repository is in ../rhel-stig-rag
mkdir -p app
cp ../rhel-stig-rag/rhel_stig_rag.py app/
cp ../rhel-stig-rag/stig_client.py app/
cp ../rhel-stig-rag/stig_data_collector.py app/
cp ../rhel-stig-rag/requirements.txt ./
```

### 6. Deploy the Container

**Standard Deployment (Rootless)**:
```bash
./deploy-podman.sh deploy
```

**If Using RHEL 8 or Experiencing Cgroups Issues**:
```bash
./deploy-podman.sh --skip-cgroups deploy
```

**For System-Wide Deployment (Rootful, requires root)**:
```bash
./deploy-podman.sh --rootful deploy
```

### 7. Verify Deployment

```bash
# Check deployment status
./manage-stig-rag.sh status

# Verify health
./manage-stig-rag.sh health

# View logs
./manage-stig-rag.sh logs
```

### 8. Enable Automatic Startup (Optional)

For the container to start automatically at boot:

**Rootless Mode**:
```bash
# Enable lingering for user session
loginctl enable-linger $USER

# Enable systemd service
systemctl --user enable stig-rag-pod.service
```

**Rootful Mode**:
```bash
sudo systemctl enable stig-rag-pod.service
```

## Directory Structure

After deployment, the following directory structure will be created:

```
~/stig-rag-data/
├── stig_data/         # STIG definition files
└── stig_chroma_db/    # Vector database storage

~/stig-rag-logs/       # Application logs

~/stig-rag-config/     # Configuration files
```

## Common Deployment Scenarios

### Basic Development Environment

```bash
./deploy-podman.sh --port 8080 deploy
```

### Production Environment

```bash
# Deploy with resource limits and production settings
./deploy-podman.sh \
  --port 8000 \
  --memory 8g \
  --cpus 4 \
  deploy
```

### High Security Environment

```bash
# Deploy with enhanced security settings
./deploy-podman.sh \
  --read-only \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  deploy
```

## Troubleshooting Common Issues

### Container Fails to Start

**Issue**: The container fails to start and you see cgroups-related errors.

**Solution**:
```bash
# Try with cgroups compatibility mode
./deploy-podman.sh --skip-cgroups deploy
```

### Service Not Accessible

**Issue**: The service is running but not accessible.

**Solution**:
```bash
# Check firewall settings
sudo firewall-cmd --list-ports

# Add required port
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### SELinux Denials

**Issue**: SELinux is blocking container operations.

**Solution**:
```bash
# Check for SELinux denials
sudo ausearch -m avc -ts recent

# Create a custom policy (if needed)
sudo audit2allow -a -M stig-rag
sudo semodule -i stig-rag.pp
```

### Out of Memory

**Issue**: Container terminates with out-of-memory errors.

**Solution**:
```bash
# Increase memory limit
./deploy-podman.sh --memory 8g deploy
```

## Updating the Container

To update the container with new application code:

```bash
# Copy updated application files
cp ../rhel-stig-rag/rhel_stig_rag.py app/
cp ../rhel-stig-rag/stig_client.py app/

# Rebuild and update the container
./manage-stig-rag.sh update
```

## Backup and Restore

### Creating a Backup

```bash
# Create a backup
./manage-stig-rag.sh backup
```

Backups are stored in `~/stig-rag-backups/`.

### Restoring from Backup

```bash
# Restore from a backup
tar -xzf ~/stig-rag-backups/stig-rag-backup-20250520_123456.tar.gz -C ~/stig-rag-data/
./manage-stig-rag.sh restart
```

## Advanced Configuration

### Using Custom LLM Providers

Edit `~/stig-rag-config/config.env` and add your API keys:

```bash
# For OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-3.5-turbo

# For Anthropic Claude
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-3-sonnet-20240229
```

### Resource Optimization

For memory-constrained environments:

```bash
# Edit config.env
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=500
CHUNK_OVERLAP=100
ENABLE_CACHING=true
CACHE_TTL_SECONDS=7200
```

## Next Steps

After successful deployment:

1. Load STIG data using `stig_client.py`
2. Test with basic queries
3. Explore the API documentation at `http://localhost:8000/docs`
4. Set up a regular backup schedule

For more detailed information, see the main [README.md](../README.md) and the [Podman Security Guide](podman-security.md).