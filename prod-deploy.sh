#!/bin/bash
# selinux-fixed-deploy.sh - Fixed for SELinux and tmpfs issues

set -e

# Colors and functions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
DATA_DIR="$HOME/stig-rag-data"
LOG_DIR="$HOME/stig-rag-logs"
CONFIG_DIR="$HOME/stig-rag-config"
CONTAINER_NAME="stig-rag"
IMAGE_NAME="localhost/rhel-stig-rag:latest"
HOST_PORT="8000"

# Check and fix SELinux issues
echo_status "Checking SELinux status..."
SELINUX_STATUS=$(getenforce 2>/dev/null || echo "Disabled")
echo "SELinux status: $SELINUX_STATUS"

if [ "$SELINUX_STATUS" != "Disabled" ]; then
    echo_warn "SELinux is enabled. Applying fixes..."
    
    # Set SELinux boolean for container use
    sudo setsebool -P container_manage_cgroup true 2>/dev/null || echo "Failed to set container_manage_cgroup"
    
    # Allow container tmpfs mounts
    sudo setsebool -P virt_use_fusefs true 2>/dev/null || echo "Failed to set virt_use_fusefs"
fi

# 1. Setup directories with proper SELinux contexts
echo_status "Creating directories with proper contexts..."
mkdir -p "$DATA_DIR"/{stig_data,stig_chroma_db}
mkdir -p "$LOG_DIR"
mkdir -p "$CONFIG_DIR"
chmod -R 755 "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"

# Set SELinux contexts if SELinux is enabled
if [ "$SELINUX_STATUS" != "Disabled" ]; then
    echo_status "Setting SELinux contexts..."
    chcon -R -t container_file_t "$DATA_DIR" 2>/dev/null || echo "Warning: Could not set SELinux context on data dir"
    chcon -R -t container_file_t "$LOG_DIR" 2>/dev/null || echo "Warning: Could not set SELinux context on log dir"
fi

# 2. Create configuration
cat > "$CONFIG_DIR/config.env" << EOF
APP_NAME=RHEL STIG RAG Assistant
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=8000
DEFAULT_RHEL_VERSION=9
LOG_LEVEL=INFO
ENABLE_CGROUPS_COMPAT=true
MALLOC_ARENA_MAX=2
EOF

# 3. Create minimal app
cat > "minimal_app.py" << 'EOF'
#!/usr/bin/env python3
import uvicorn
from fastapi import FastAPI

app = FastAPI(title="RHEL STIG RAG Assistant")

@app.get("/")
def root():
    return {"name": "RHEL STIG RAG Assistant", "status": "running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    print("Starting RHEL STIG RAG application...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

echo "fastapi==0.104.0" > requirements.txt
echo "uvicorn==0.24.0" >> requirements.txt

# 4. Create start script
cat > "container_start.sh" << 'EOF'
#!/bin/bash
echo "Starting RHEL STIG RAG container..."
exec python3 /app/app.py
EOF
chmod +x container_start.sh

# 5. Create SELinux-compatible Containerfile
cat > "Containerfile.selinux" << 'EOF'
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest

# Environment variables
ENV _CONTAINERS_USERNS_CONFIGURED=1
ENV PYTHONUNBUFFERED=1

# Install packages
RUN microdnf update -y && \
    microdnf install -y python3 python3-pip && \
    microdnf clean all

WORKDIR /app

# Copy and install requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY minimal_app.py /app/app.py
COPY container_start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create directories
RUN mkdir -p /app/stig_data /app/stig_chroma_db /app/logs

EXPOSE 8000
CMD ["/app/start.sh"]
EOF

# 6. Build image
echo_status "Building container image..."
podman build -t "$IMAGE_NAME" -f Containerfile.selinux .

# 7. Remove any existing container
podman rm -f "$CONTAINER_NAME" 2>/dev/null || true

# 8. Run container with SELinux and tmpfs fixes
echo_status "Starting container with SELinux fixes..."
podman run -d \
    --name "$CONTAINER_NAME" \
    -p "$HOST_PORT:8000" \
    --env-file "$CONFIG_DIR/config.env" \
    --volume "$DATA_DIR/stig_data:/app/stig_data:Z" \
    --volume "$DATA_DIR/stig_chroma_db:/app/stig_chroma_db:Z" \
    --volume "$LOG_DIR:/app/logs:Z" \
    --security-opt label=disable \
    --shm-size=128m \
    --tmpfs /tmp:noexec,nosuid,size=100m \
    --restart unless-stopped \
    "$IMAGE_NAME"

# 9. Create FIXED systemd service
SERVICE_DIR="$HOME/.config/systemd/user"
mkdir -p "$SERVICE_DIR"

cat > "$SERVICE_DIR/stig-rag.service" << EOF
[Unit]
Description=RHEL STIG RAG Container
After=network.target
Wants=network.target

[Service]
Type=simple
Restart=on-failure
RestartSec=10
# Use 'start -a' instead of just 'start'
ExecStart=/usr/bin/podman start -a $CONTAINER_NAME
ExecStop=/usr/bin/podman stop -t 10 $CONTAINER_NAME
# Environment for SELinux
Environment="SELINUX=disabled"
# Kill mode
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=default.target
EOF

# 10. Enable service with proper user session
systemctl --user daemon-reload
systemctl --user enable stig-rag.service

# Enable lingering for user session persistence
loginctl enable-linger $USER

echo_status "Systemd service created. Testing manual container start first..."

# 11. Test the container
sleep 5
if podman ps --filter "name=$CONTAINER_NAME" | grep -q "$CONTAINER_NAME"; then
    echo_status "Container is running. Testing health..."
    
    for i in {1..15}; do
        if curl -s -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
            echo_status "✅ Container working! Service available at http://localhost:$HOST_PORT"
            echo_status "Container logs:"
            podman logs "$CONTAINER_NAME" | tail -n 10
            
            echo_status "Now testing systemd service..."
            # Stop the manual container
            podman stop "$CONTAINER_NAME"
            sleep 2
            
            # Start via systemd
            systemctl --user start stig-rag.service
            sleep 5
            
            # Check if it's working via systemd
            if curl -s -f "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
                echo_status "✅ Systemd service working correctly!"
                echo_status "Service status:"
                systemctl --user status stig-rag.service --no-pager
            else
                echo_error "❌ Systemd service failed. Checking status..."
                systemctl --user status stig-rag.service --no-pager
                journalctl --user -u stig-rag.service -n 20
            fi
            exit 0
        fi
        echo -n "."
        sleep 2
    done
    
    echo_error "Container started but health check failed"
    podman logs "$CONTAINER_NAME"
else
    echo_error "Container failed to start"
    podman logs "$CONTAINER_NAME" 2>/dev/null || echo "No logs available"
fi
