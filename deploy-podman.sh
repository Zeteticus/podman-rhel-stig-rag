#!/bin/bash

# RHEL STIG RAG Podman Deployment Script - With cgroups fixes
# Supports both rootless and rootful deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
DEPLOYMENT_MODE="rootless"
CONTAINER_NAME="stig-rag"
POD_NAME="stig-rag-pod"
IMAGE_NAME="localhost/rhel-stig-rag:latest"
HOST_PORT="8000"
CONTAINER_PORT="8000"
DATA_DIR="$HOME/stig-rag-data"
LOG_DIR="$HOME/stig-rag-logs"
CONFIG_DIR="$HOME/stig-rag-config"
NETWORK_NAME="stig-rag-net"
CGROUP_MANAGER="systemd"  # Use systemd cgroup manager by default
SKIP_CGROUPS_CHECK="false"

# Functions
print_header() {
    echo -e "${BLUE}=====================================${NC}"
    echo -e "${BLUE}  RHEL STIG RAG Podman Deployment   ${NC}"
    echo -e "${BLUE}=====================================${NC}"
}

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  build       Build the container image"
    echo "  deploy      Deploy the STIG RAG system"
    echo "  start       Start existing containers"
    echo "  stop        Stop running containers"
    echo "  restart     Restart containers"
    echo "  status      Show status of containers"
    echo "  logs        Show container logs"
    echo "  cleanup     Remove containers and images"
    echo "  update      Update container with new image"
    echo ""
    echo "Options:"
    echo "  --rootful          Use rootful containers (requires sudo)"
    echo "  --rootless         Use rootless containers (default)"
    echo "  --pod-name NAME    Specify pod name (default: stig-rag-pod)"
    echo "  --port PORT        Specify host port (default: 8000)"
    echo "  --data-dir DIR     Specify data directory"
    echo "  --cgroup-manager   Specify cgroup manager (systemd or cgroupfs)"
    echo "  --skip-cgroups     Skip cgroups checks (use for problematic environments)"
    echo "  --help             Show this help message"
}

check_podman() {
    if ! command -v podman &> /dev/null; then
        print_error "Podman is not installed. Please install Podman first."
        echo "For RHEL/CentOS: sudo dnf install podman"
        echo "For Ubuntu: sudo apt install podman"
        exit 1
    fi
    print_status "Podman version: $(podman --version)"
}

check_cgroups() {
    print_status "Checking cgroups configuration..."
    
    if [ "$SKIP_CGROUPS_CHECK" = "true" ]; then
        print_warning "Skipping cgroups checks as requested"
        return 0
    fi
    
    # Check cgroup version
    if [ -f /sys/fs/cgroup/cgroup.controllers ]; then
        print_status "System is using cgroups v2 (unified hierarchy)"
        CGROUP_VERSION="v2"
    else
        print_status "System is using cgroups v1 (legacy)"
        CGROUP_VERSION="v1"
    fi
    
    # Check if running inside a container
    if grep -q docker /proc/1/cgroup || grep -q lxc /proc/1/cgroup; then
        print_warning "Running inside a container. This might cause cgroups issues."
        print_warning "Consider using '--skip-cgroups' option if you encounter problems."
    fi
    
    # Check if memory controller is available (important for resource limits)
    if [ "$CGROUP_VERSION" = "v2" ]; then
        if ! grep -q memory /sys/fs/cgroup/cgroup.controllers; then
            print_warning "Memory controller not available in cgroups v2. Resource limits may not work."
        fi
    else
        if [ ! -d "/sys/fs/cgroup/memory" ]; then
            print_warning "Memory controller not available in cgroups v1. Resource limits may not work."
        fi
    fi
    
    # Set appropriate cgroup manager based on environment
    if [ "$CGROUP_VERSION" = "v2" ]; then
        # For cgroups v2, systemd is usually better
        CGROUP_MANAGER="systemd"
    else
        # For cgroups v1, especially in problematic environments, cgroupfs can work better
        CGROUP_MANAGER="cgroupfs"
    fi
    
    print_status "Using cgroup manager: $CGROUP_MANAGER"
}

setup_directories() {
    print_status "Setting up directories..."
    
    mkdir -p "$DATA_DIR"/{stig_data,stig_chroma_db}
    mkdir -p "$LOG_DIR"
    mkdir -p "$CONFIG_DIR"
    
    # Set permissions for rootless containers
    if [[ "$DEPLOYMENT_MODE" == "rootless" ]]; then
        chmod -R 755 "$DATA_DIR" "$LOG_DIR" "$CONFIG_DIR"
    fi
    
    print_status "Directories created: $DATA_DIR, $LOG_DIR, $CONFIG_DIR"
}

create_network() {
    print_status "Creating Podman network..."
    
    if ! podman network exists "$NETWORK_NAME" 2>/dev/null; then
        podman network create "$NETWORK_NAME"
        print_status "Network '$NETWORK_NAME' created"
    else
        print_status "Network '$NETWORK_NAME' already exists"
    fi
}

build_image() {
    print_status "Building STIG RAG container image..."
    
    if [[ ! -f "Containerfile" ]]; then
        print_error "Containerfile not found in current directory"
        exit 1
    fi
    
    # Add additional build arguments for cgroups compatibility
    podman build \
        --build-arg SKIP_CGROUPS_CHECK="$SKIP_CGROUPS_CHECK" \
        -t "$IMAGE_NAME" .
        
    print_status "Image '$IMAGE_NAME' built successfully"
}

create_config() {
    print_status "Creating configuration files..."
    
    cat > "$CONFIG_DIR/config.env" << EOF
# STIG RAG Configuration
APP_NAME=RHEL STIG RAG Assistant
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=$CONTAINER_PORT

# RHEL Version Priority
DEFAULT_RHEL_VERSION=9
SUPPORTED_RHEL_VERSIONS=8,9

# Directories (container paths)
STIG_DATA_DIR=/app/stig_data
VECTORSTORE_PATH=/app/stig_chroma_db
LOG_DIR=/app/logs

# Vector Store Settings
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Language Model Settings
LLM_PROVIDER=huggingface
LLM_MODEL=microsoft/DialoGPT-medium
LLM_TEMPERATURE=0.1
LLM_MAX_LENGTH=2048

# Search Settings
DEFAULT_SEARCH_RESULTS=5
MAX_SEARCH_RESULTS=20
PREFER_RHEL9_RESULTS=true

# Logging
LOG_LEVEL=INFO

# Performance Settings
ENABLE_CACHING=true
CACHE_TTL_SECONDS=3600

# Security Settings
ALLOWED_FILE_EXTENSIONS=.xml,.json,.txt
MAX_FILE_SIZE_MB=50
ENABLE_CORS=true
ALLOWED_ORIGINS=*

# Cgroups Compatibility Settings
ENABLE_CGROUPS_COMPAT=true
MALLOC_ARENA_MAX=2
EOF

    print_status "Configuration created: $CONFIG_DIR/config.env"
}

create_pod() {
    print_status "Creating STIG RAG pod..."
    
    if podman pod exists "$POD_NAME" 2>/dev/null; then
        print_warning "Pod '$POD_NAME' already exists. Removing..."
        podman pod rm -f "$POD_NAME"
    fi
    
    podman pod create \
        --name "$POD_NAME" \
        --publish "$HOST_PORT:$CONTAINER_PORT" \
        --network "$NETWORK_NAME"
    
    print_status "Pod '$POD_NAME' created"
}

deploy_container() {
    print_status "Deploying STIG RAG container..."
    
    # Remove existing container if it exists
    if podman container exists "$CONTAINER_NAME" 2>/dev/null; then
        print_warning "Container '$CONTAINER_NAME' already exists. Removing..."
        podman rm -f "$CONTAINER_NAME"
    fi
    
    # Add cgroups-specific options
    CGROUP_OPTS=""
    SECURITY_OPTS=""
    
    if [ "$SKIP_CGROUPS_CHECK" = "true" ]; then
        # Add options to bypass cgroups issues
        CGROUP_OPTS="--cgroup-manager=cgroupfs"
        SECURITY_OPTS="--security-opt seccomp=unconfined"
    else
        # Use detected cgroup manager
        CGROUP_OPTS="--cgroup-manager=$CGROUP_MANAGER"
    fi
    
    # Run the container with extra options for cgroups compatibility
    podman run -d \
        --name "$CONTAINER_NAME" \
        --pod "$POD_NAME" \
        --env-file "$CONFIG_DIR/config.env" \
        --volume "$DATA_DIR/stig_data:/app/stig_data:Z" \
        --volume "$DATA_DIR/stig_chroma_db:/app/stig_chroma_db:Z" \
        --volume "$LOG_DIR:/app/logs:Z" \
        --label "app=stig-rag" \
        --label "version=1.0.0" \
        $CGROUP_OPTS \
        $SECURITY_OPTS \
        --restart unless-stopped \
        "$IMAGE_NAME"
    
    print_status "Container '$CONTAINER_NAME' deployed"
}

setup_systemd_service() {
    print_status "Setting up systemd service for automatic startup..."
    
    local service_dir
    if [[ "$DEPLOYMENT_MODE" == "rootless" ]]; then
        service_dir="$HOME/.config/systemd/user"
        mkdir -p "$service_dir"
    else
        service_dir="/etc/systemd/system"
    fi
    
    # Create systemd service for the pod with proper cgroups handling
    cat > "$service_dir/stig-rag-pod.service" << EOF
[Unit]
Description=STIG RAG Pod
Wants=network-online.target
After=network-online.target
RequiresMountsFor=%t/containers

[Service]
Environment=PODMAN_SYSTEMD_UNIT=%n
Restart=on-failure
TimeoutStopSec=70
# Cgroups compatibility settings
Environment="ENABLE_CGROUPS_COMPAT=1"
Environment="MALLOC_ARENA_MAX=2"
ExecStartPre=/bin/rm -f %t/%n.ctr-id
ExecStart=/usr/bin/podman pod start $POD_NAME
ExecStop=/usr/bin/podman pod stop -t 10 $POD_NAME
ExecStopPost=/bin/rm -f %t/%n.ctr-id
PIDFile=%t/%n.pid
Type=forking

[Install]
WantedBy=default.target
EOF

    # Reload systemd and enable service
    if [[ "$DEPLOYMENT_MODE" == "rootless" ]]; then
        systemctl --user daemon-reload
        systemctl --user enable stig-rag-pod.service
        print_status "Rootless systemd service enabled"
        print_status "To start on boot: loginctl enable-linger $USER"
    else
        sudo systemctl daemon-reload
        sudo systemctl enable stig-rag-pod.service
        print_status "Rootful systemd service enabled"
    fi
}

create_sample_data() {
    print_status "Creating sample STIG data..."
    
    # RHEL 9 Sample Data
    cat > "$DATA_DIR/stig_data/sample_rhel9_stig.json" << 'EOF'
{
  "version": "RHEL-9-STIG-V1R3",
  "release_date": "2024-01-01",
  "rhel_version": "9",
  "priority": 1,
  "controls": [
    {
      "id": "RHEL-09-211010",
      "title": "RHEL 9 must be configured to verify the signature of packages",
      "severity": "high",
      "version": "9",
      "description": "Changes to any software components can have significant effects on the overall security of the operating system.",
      "check": "Verify Red Hat GPG signature checking is configured with: $ sudo grep gpgcheck /etc/dnf/dnf.conf",
      "fix": "Configure Red Hat package signature checking by editing /etc/dnf/dnf.conf and ensure: gpgcheck=1",
      "references": ["CCI-001749"],
      "category": "Package Management"
    },
    {
      "id": "RHEL-09-211015",
      "title": "RHEL 9 must have the gpgcheck enabled for all repositories",
      "severity": "high",
      "version": "9",
      "description": "Changes to any software components can have significant effects on the overall security of the operating system.",
      "check": "Verify that gpgcheck is enabled for all repositories in /etc/yum.repos.d/",
      "fix": "Edit each repository file in /etc/yum.repos.d/ and ensure gpgcheck=1",
      "references": ["CCI-001749"],
      "category": "Package Management"
    }
  ]
}
EOF

    # RHEL 8 Sample Data
    cat > "$DATA_DIR/stig_data/sample_rhel8_stig.json" << 'EOF'
{
  "version": "RHEL-8-STIG-V1R12",
  "release_date": "2023-01-01",
  "rhel_version": "8",
  "priority": 2,
  "controls": [
    {
      "id": "RHEL-08-010010",
      "title": "RHEL 8 must be configured to verify the signature of packages",
      "severity": "high",
      "version": "8",
      "description": "Changes to any software components can have significant effects on the overall security of the operating system.",
      "check": "Verify Red Hat GPG signature checking is configured with: $ sudo grep gpgcheck /etc/yum.conf",
      "fix": "Configure Red Hat package signature checking by editing /etc/yum.conf and ensure: gpgcheck=1",
      "references": ["CCI-001749"],
      "category": "Package Management"
    }
  ]
}
EOF

    print_status "Sample STIG data created"
}

wait_for_service() {
    print_status "Waiting for STIG RAG service to be ready..."
    
    local max_attempts=60  # Increased for cgroups issues
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -sf "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
            print_status "Service is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        ((attempt++))
    done
    
    print_error "Service failed to start within timeout"
    print_status "Checking for cgroups-related errors..."
    
    # Check container logs for cgroups-related issues
    if podman logs "$CONTAINER_NAME" 2>&1 | grep -i "cgroup"; then
        print_warning "Cgroups-related errors detected. Consider using --skip-cgroups option"
        print_warning "Example: $0 --skip-cgroups deploy"
    fi
    
    return 1
}

load_sample_data() {
    print_status "Loading sample STIG data..."
    
    # Load RHEL 9 data (primary)
    curl -X POST "http://localhost:$HOST_PORT/load-stig" \
         -d "file_path=/app/stig_data/sample_rhel9_stig.json" \
         2>/dev/null || print_warning "Failed to load RHEL 9 sample data"
    
    # Load RHEL 8 data (secondary)
    curl -X POST "http://localhost:$HOST_PORT/load-stig" \
         -d "file_path=/app/stig_data/sample_rhel8_stig.json" \
         2>/dev/null || print_warning "Failed to load RHEL 8 sample data"
    
    print_status "Sample data loading completed"
}

test_deployment() {
    print_status "Testing deployment..."
    
    # Test health endpoint
    if curl -sf "http://localhost:$HOST_PORT/health" >/dev/null; then
        print_status "Health check: PASSED"
    else
        print_error "Health check: FAILED"
        return 1
    fi
    
    # Test query endpoint
    local response=$(curl -s -X POST "http://localhost:$HOST_PORT/query" \
                    -H "Content-Type: application/json" \
                    -d '{"question": "How do I verify GPG signatures?", "rhel_version": "9"}')
    
    if echo "$response" | grep -q "answer"; then
        print_status "Query test: PASSED"
    else
        print_error "Query test: FAILED"
        return 1
    fi
    
    print_status "All tests passed!"
}

show_status() {
    print_status "STIG RAG System Status:"
    echo
    
    echo "Pod Status:"
    podman pod ps --filter name="$POD_NAME" 2>/dev/null || echo "Pod not found"
    echo
    
    echo "Container Status:"
    podman ps --filter name="$CONTAINER_NAME" 2>/dev/null || echo "Container not found"
    echo
    
    if podman container exists "$CONTAINER_NAME" 2>/dev/null; then
        echo "Container Health:"
        podman healthcheck run "$CONTAINER_NAME" 2>/dev/null || echo "Health check failed"
        echo
        
        # Show cgroups information
        echo "Cgroups Configuration:"
        podman exec "$CONTAINER_NAME" cat /proc/1/cgroup 2>/dev/null || echo "Failed to get cgroups info"
        echo
    fi
    
    if curl -sf "http://localhost:$HOST_PORT/health" >/dev/null 2>&1; then
        echo "Service Status: HEALTHY"
        echo "Service URL: http://localhost:$HOST_PORT"
        echo "API Docs: http://localhost:$HOST_PORT/docs"
    else
        echo "Service Status: UNHEALTHY or NOT RUNNING"
    fi
}

show_logs() {
    local follow_flag=""
    if [[ "$1" == "-f" || "$1" == "--follow" ]]; then
        follow_flag="-f"
    fi
    
    if podman container exists "$CONTAINER_NAME" 2>/dev/null; then
        podman logs $follow_flag "$CONTAINER_NAME"
    else
        print_error "Container '$CONTAINER_NAME' not found"
    fi
}

start_containers() {
    print_status "Starting containers..."
    
    if podman pod exists "$POD_NAME" 2>/dev/null; then
        podman pod start "$POD_NAME"
        print_status "Pod '$POD_NAME' started"
    else
        print_error "Pod '$POD_NAME' not found. Run deploy first."
    fi
}

stop_containers() {
    print_status "Stopping containers..."
    
    if podman pod exists "$POD_NAME" 2>/dev/null; then
        podman pod stop "$POD_NAME"
        print_status "Pod '$POD_NAME' stopped"
    else
        print_warning "Pod '$POD_NAME' not found"
    fi
}

restart_containers() {
    print_status "Restarting containers..."
    stop_containers
    sleep 2
    start_containers
}

cleanup() {
    print_warning "Cleaning up containers and images..."
    
    # Stop and remove pod
    if podman pod exists "$POD_NAME" 2>/dev/null; then
        podman pod rm -f "$POD_NAME"
        print_status "Pod '$POD_NAME' removed"
    fi
    
    # Remove network
    if podman network exists "$NETWORK_NAME" 2>/dev/null; then
        podman network rm "$NETWORK_NAME"
        print_status "Network '$NETWORK_NAME' removed"
    fi
    
    # Remove image (optional)
    read -p "Remove image '$IMAGE_NAME'? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        podman rmi "$IMAGE_NAME" 2>/dev/null || print_warning "Image not found"
    fi
    
    print_status "Cleanup completed"
}

update_deployment() {
    print_status "Updating deployment with new image..."
    
    # Build new image
    build_image
    
    # Stop existing containers
    stop_containers
    
    # Remove container (but keep pod)
    if podman container exists "$CONTAINER_NAME" 2>/dev/null; then
        podman rm "$CONTAINER_NAME"
    fi
    
    # Deploy new container
    deploy_container
    
    # Wait for service and test
    wait_for_service
    test_deployment
    
    print_status "Update completed successfully"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --rootful)
            DEPLOYMENT_MODE="rootful"
            shift
            ;;
        --rootless)
            DEPLOYMENT_MODE="rootless"
            shift
            ;;
        --pod-name)
            POD_NAME="$2"
            shift 2
            ;;
        --port)
            HOST_PORT="$2"
            shift 2
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --cgroup-manager)
            CGROUP_MANAGER="$2"
            shift 2
            ;;
        --skip-cgroups)
            SKIP_CGROUPS_CHECK="true"
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            COMMAND="$1"
            shift
            ;;
    esac
done

# Adjust paths and commands for rootful mode
if [[ "$DEPLOYMENT_MODE" == "rootful" ]]; then
    DATA_DIR="/opt/stig-rag-data"
    LOG_DIR="/var/log/stig-rag"
    CONFIG_DIR="/etc/stig-rag"
    
    # Add sudo for directory creation and file operations
    if [[ "$COMMAND" == "deploy" ]]; then
        print_warning "Rootful mode requires sudo privileges"
    fi
fi

# Main execution
print_header
check_podman

# If not skipping cgroups check, check the configuration
if [ "$SKIP_CGROUPS_CHECK" != "true" ]; then
    check_cgroups
fi

case "${COMMAND:-}" in
    build)
        build_image
        ;;
    deploy)
        setup_directories
        create_network
        build_image
        create_config
        create_sample_data
        create_pod
        deploy_container
        setup_systemd_service
        wait_for_service
        load_sample_data
        test_deployment
        echo
        print_status "STIG RAG deployment completed successfully!"
        print_status "Service URL: http://localhost:$HOST_PORT"
        print_status "API Documentation: http://localhost:$HOST_PORT/docs"
        print_status "Try: curl http://localhost:$HOST_PORT/health"
        
        # Display cgroups help if using special options
        if [ "$SKIP_CGROUPS_CHECK" = "true" ]; then
            print_warning "Note: Running with --skip-cgroups option. Some resource limitations may not work."
            print_warning "For production use, consider fixing the cgroups configuration."
        fi
        ;;
    start)
        start_containers
        ;;
    stop)
        stop_containers
        ;;
    restart)
        restart_containers
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$@"
        ;;
    cleanup)
        cleanup
        ;;
    update)
        update_deployment
        ;;
    *)
        usage
        exit 1
        ;;
esac
