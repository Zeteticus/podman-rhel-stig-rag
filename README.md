# Podman RHEL STIG RAG Deployment

![RHEL](https://img.shields.io/badge/RHEL-9%20%7C%208-EE0000)
![Podman](https://img.shields.io/badge/Podman-4.0%2B-892CA0)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-009688)
![License](https://img.shields.io/badge/License-MIT-blue)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen)

> **Secure, rootless Podman deployment for the RHEL STIG RAG system with enhanced web interface and comprehensive RHEL 9 support.**

## 🚀 Overview

This project provides a production-ready Podman containerization solution for the RHEL Security Technical Implementation Guide (STIG) Retrieval-Augmented Generation system. It features rootless deployment, SELinux integration, and an enhanced web interface optimized for RHEL security compliance workflows.

### ✨ Key Features

- **🛡️ Rootless Security**: Enhanced security through user namespaces and non-privileged containers
- **🎯 RHEL 9 Priority**: Optimized for RHEL 9 with comprehensive RHEL 8 legacy support
- **🌐 Enhanced Web Interface**: Professional web UI with interactive forms and detailed guidance
- **🔍 Smart STIG Responses**: Context-aware responses for common STIG compliance topics
- **📱 Responsive Design**: Works seamlessly on desktop and mobile devices
- **🔗 REST API**: Full programmatic access with interactive documentation
- **⚙️ Production Ready**: Systemd integration, auto-restart, and monitoring capabilities

## 📸 Screenshots

### Main Interface
The enhanced web interface provides an intuitive way to ask STIG compliance questions:

- **Interactive Query Form**: Ask questions in natural language
- **RHEL Version Selection**: Choose between RHEL 9 (primary) and RHEL 8 (legacy)
- **STIG ID Support**: Target specific STIG controls
- **Example Questions**: Built-in suggestions for common compliance scenarios

### Enhanced Responses
Get detailed, actionable guidance with:

- **Step-by-step Implementation**: Clear instructions for STIG compliance
- **Code Examples**: Real command-line examples for RHEL configuration
- **Version-Specific Guidance**: Tailored advice for your RHEL version
- **Visual Formatting**: Color-coded sections for easy reading

## 🚀 Quick Start

### Prerequisites

- RHEL 8/9, CentOS, or Fedora
- Podman 3.0+ installed
- 4GB RAM minimum (8GB recommended)
- 5GB free disk space

### One-Command Deployment

```bash
# Clone and deploy in one step
git clone https://github.com/your-username/podman-rhel-stig-rag.git
cd podman-rhel-stig-rag
chmod +x upgrade-to-full.sh
./upgrade-to-full.sh
```

### Manual Deployment

```bash
# 1. Clone the repository
git clone https://github.com/your-username/podman-rhel-stig-rag.git
cd podman-rhel-stig-rag

# 2. Install Podman (if not already installed)
sudo dnf install -y podman

# 3. Deploy the enhanced version
chmod +x upgrade-to-full.sh
./upgrade-to-full.sh

# 4. Access the web interface
open http://localhost:8000
```

## 🌟 What You Get

After deployment, you'll have access to:

| Feature | Endpoint | Description |
|---------|----------|-------------|
| **Web Interface** | `http://localhost:8000` | Interactive web form for STIG questions |
| **API Documentation** | `http://localhost:8000/docs` | Swagger UI for REST API |
| **Health Check** | `http://localhost:8000/health` | System status monitoring |
| **Direct API** | `http://localhost:8000/api/query` | Programmatic access |

## 💡 Usage Examples

### Web Interface

1. **Navigate** to `http://localhost:8000`
2. **Enter your question**: "How do I configure GPG signature verification in RHEL 9?"
3. **Select RHEL version**: Choose RHEL 9 or RHEL 8
4. **Optional**: Specify a STIG ID like `RHEL-09-211010`
5. **Submit** and get detailed guidance with code examples

### API Usage

```bash
# Health check
curl http://localhost:8000/health

# Query STIG information
curl -X POST "http://localhost:8000/api/query" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I configure SELinux for STIG compliance?",
    "rhel_version": "9",
    "stig_id": "RHEL-09-232010"
  }'

# Search by STIG ID
curl http://localhost:8000/search/RHEL-09-211010
```

### Example Questions to Try

- **Package Security**: "How do I verify GPG signatures for packages in RHEL 9?"
- **Access Control**: "What are the SELinux requirements for RHEL compliance?"
- **Boot Security**: "How do I configure secure boot and UEFI settings?"
- **Version Comparison**: "What are the key differences between RHEL 8 and RHEL 9 STIG requirements?"
- **Specific Controls**: "How do I implement RHEL-09-211010?"

## ⚙️ Configuration

### Environment Variables

Customize your deployment by editing `~/stig-rag-config/config.env`:

```bash
# Application Settings
APP_NAME=RHEL STIG RAG Assistant
APP_PORT=8000
DEFAULT_RHEL_VERSION=9

# Performance Settings
ENABLE_CACHING=true
CACHE_TTL_SECONDS=3600
MALLOC_ARENA_MAX=2

# Logging
LOG_LEVEL=INFO
```

### Advanced Configuration

#### Custom Port

```bash
# Deploy on a different port
./upgrade-to-full.sh --port 8080
```

#### Resource Limits

```bash
# Deploy with custom resource limits
podman run -d \
  --name stig-rag \
  -p 8000:8000 \
  --memory=4g \
  --cpus=2 \
  localhost/rhel-stig-rag:latest
```

#### SELinux Contexts

The deployment automatically handles SELinux contexts, but you can verify:

```bash
# Check SELinux contexts
ls -Z ~/stig-rag-data/
```

## 🛠️ Management

### Container Management

```bash
# Check status
podman ps --filter name=stig-rag

# View logs
podman logs stig-rag

# Stop container
podman stop stig-rag

# Start container
podman start stig-rag

# Restart container
podman restart stig-rag
```

### Systemd Service Management

```bash
# Check service status
systemctl --user status stig-rag.service

# Start service
systemctl --user start stig-rag.service

# Stop service
systemctl --user stop stig-rag.service

# Enable auto-start
systemctl --user enable stig-rag.service
```

### Updates

```bash
# Update to latest version
git pull origin main
./upgrade-to-full.sh
```

## 🔧 Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check for port conflicts
ss -tulpn | grep 8000

# Check container logs
podman logs stig-rag

# Check SELinux denials
sudo ausearch -m avc -ts recent
```

#### SELinux Issues

```bash
# Check SELinux status
getenforce

# Set SELinux to permissive (temporary fix)
sudo setenforce 0

# Fix SELinux contexts
chcon -R -t container_file_t ~/stig-rag-data/
```

#### Network Issues

```bash
# Check firewall
sudo firewall-cmd --list-ports

# Add port to firewall
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

#### Permission Issues

```bash
# Fix directory permissions
chmod -R 755 ~/stig-rag-data/
chmod -R 755 ~/stig-rag-logs/
```

### Debug Mode

Enable debug logging for troubleshooting:

```bash
# Edit configuration
echo "LOG_LEVEL=DEBUG" >> ~/stig-rag-config/config.env

# Restart container
podman restart stig-rag

# View debug logs
podman logs stig-rag | grep DEBUG
```

## 🏗️ Architecture

### Container Stack

```
┌─────────────────────────────────────┐
│           Web Browser               │
└─────────────────┬───────────────────┘
                  │ HTTP :8000
┌─────────────────▼───────────────────┐
│         Podman Container            │
│  ┌─────────────────────────────┐    │
│  │       FastAPI App           │    │
│  │   Enhanced Web Interface    │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │      STIG RAG Logic         │    │
│  │   (Placeholder/Enhanced)    │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

### Security Model

- **Rootless Containers**: No root privileges required
- **User Namespaces**: Container processes mapped to unprivileged host users
- **SELinux Integration**: Automatic context labeling with `:Z` volumes
- **Read-only Layers**: Container filesystem layers are immutable
- **Minimal Attack Surface**: UBI minimal base image

## 🎯 RHEL Version Support

### RHEL 9 (Primary Focus)

- **Optimized Interface**: Primary focus on RHEL 9 STIG controls
- **Enhanced Guidance**: Detailed implementation steps for RHEL 9 features
- **Modern Security**: Support for latest RHEL 9 security features

### RHEL 8 (Legacy Support)

- **Backward Compatibility**: Full support for RHEL 8 STIG requirements
- **Migration Guidance**: Recommendations for upgrading to RHEL 9
- **Maintained Functionality**: All core features work with RHEL 8

## 🔮 Integration with Main Project

This Podman deployment project is designed to work with the [main RHEL STIG RAG system](https://github.com/your-username/rhel-stig-rag). To integrate:

1. **Development**: Use this for quick prototyping and testing
2. **Production**: Deploy this for secure, scalable STIG assistance
3. **Integration**: Connect to the main project's AI pipeline when ready

### Upgrade Path

```bash
# Clone both repositories
git clone https://github.com/your-username/rhel-stig-rag.git
git clone https://github.com/your-username/podman-rhel-stig-rag.git

# Copy full application code
cp rhel-stig-rag/app/* podman-rhel-stig-rag/

# Rebuild with full functionality
cd podman-rhel-stig-rag
./upgrade-to-full.sh
```

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Fork and clone
git clone https://github.com/your-username/podman-rhel-stig-rag.git
cd podman-rhel-stig-rag

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and test
./upgrade-to-full.sh

# Commit and push
git commit -m "Add amazing feature"
git push origin feature/amazing-feature
```

### Contribution Guidelines

- **Security First**: All changes must maintain or improve security posture
- **RHEL Focus**: Prioritize RHEL 9 with backward compatibility for RHEL 8
- **Testing**: Test on multiple RHEL versions and configurations
- **Documentation**: Update README and docs for any new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- **[Red Hat](https://www.redhat.com/)** - For RHEL and Podman
- **[DISA](https://public.cyber.mil/stigs/)** - For STIG documentation
- **[Podman Project](https://podman.io/)** - For rootless container technology
- **[FastAPI](https://fastapi.tiangolo.com/)** - For the web framework
- **[Main RHEL STIG RAG Project](https://github.com/your-username/rhel-stig-rag)** - Core functionality

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/podman-rhel-stig-rag/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/podman-rhel-stig-rag/discussions)
- **Security**: Report security issues privately to [security@yourorg.com]

## 🗺️ Roadmap

- [ ] **Full RAG Integration**: Connect to vector database and AI models
- [ ] **STIG Data Loader**: Automatic DISA STIG document processing
- [ ] **Advanced Search**: Semantic search across STIG controls
- [ ] **Compliance Dashboard**: Visual compliance status tracking
- [ ] **Multi-tenant Support**: Support for multiple organizations
- [ ] **API Authentication**: Secure API access with tokens
- [ ] **Kubernetes Support**: Helm charts for Kubernetes deployment

---

<p align="center">
  <strong>🛡️ Secure your Red Hat infrastructure with confidence.</strong><br>
  <em>Deploy securely, comply confidently, operate efficiently.</em>
</p>

---

**Quick Links**: [🌐 Demo](http://localhost:8000) | [📚 API Docs](http://localhost:8000/docs) | [🔍 Health](http://localhost:8000/health) | [📖 Main Project](https://github.com/your-username/rhel-stig-rag)
