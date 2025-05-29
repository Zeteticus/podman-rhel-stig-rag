#!/bin/bash

# Optimized STIG RAG Deployment Script with Data Loading
# This script builds and deploys the RHEL STIG RAG container with:
# - Automatic STIG JSON data loading
# - Redis caching for performance
# - Semantic search capabilities

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="stig-rag"
REDIS_NAME="stig-rag-redis"
POD_NAME="stig-rag-pod"
IMAGE_NAME="rhel-stig-rag:optimized"
PORT="${PORT:-8000}"
REDIS_PORT="${REDIS_PORT:-6379}"
DATA_DIR="${HOME}/stig-rag-data"
CACHE_DIR="${HOME}/stig-rag-cache"
LOG_DIR="${HOME}/stig-rag-logs"

# Functions
print_status() {
    echo -e "${BLUE}[*]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check for podman
    if ! command -v podman &> /dev/null; then
        print_error "Podman is not installed. Please install podman first."
        echo "Run: sudo dnf install -y podman"
        exit 1
    fi
    
    # Check for required files
    local required_files=("Dockerfile" "app.py" "load_stig_data.py" "requirements.txt" "startup.sh")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "Required file '$file' not found!"
            exit 1
        fi
    done
    
    # Check for STIG data file
    if [ ! -f "stig_data.json" ]; then
        print_warning "stig_data.json not found. Please ensure you have your STIG data file."
        echo "The container will fail to start without this file."
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    print_success "Prerequisites check passed"
}

# Create directories
create_directories() {
    print_status "Creating directories..."
    mkdir -p "$DATA_DIR" "$CACHE_DIR" "$LOG_DIR"
    
    # Set proper permissions
    chmod 755 "$DATA_DIR" "$CACHE_DIR" "$LOG_DIR"
    
    # Handle SELinux contexts if enabled
    if command -v getenforce &> /dev/null && [ "$(getenforce)" != "Disabled" ]; then
        print_status "Setting SELinux contexts..."
        chcon -R -t container_file_t "$DATA_DIR" "$CACHE_DIR" "$LOG_DIR" 2>/dev/null || true
    fi
    
    print_success "Directories created"
}

# Stop existing containers
stop_existing() {
    print_status "Stopping existing containers..."
    
    # Stop and remove existing containers
    podman stop "$APP_NAME" "$REDIS_NAME" 2>/dev/null || true
    podman rm "$APP_NAME" "$REDIS_NAME" 2>/dev/null || true
    
    # Remove existing pod
    podman pod rm "$POD_NAME" 2>/dev/null || true
    
    print_success "Existing containers stopped"
}

# Build container image
build_image() {
    print_status "Building container image..."
    
    # Make scripts executable
    chmod +x startup.sh load_stig_data.py
    
    # Build the image
    if podman build -t "$IMAGE_NAME" .; then
        print_success "Container image built successfully"
    else
        print_error "Failed to build container image"
        exit 1
    fi
}

# Create pod for networking
create_pod() {
    print_status "Creating pod for container networking..."
    
    podman pod create \
        --name "$POD_NAME" \
        -p "${PORT}:8000" \
        -p "${REDIS_PORT}:6379" \
        --userns=keep-id \
        --network bridge
    
    print_success "Pod created"
}

# Run Redis container
run_redis() {
    print_status "Starting Redis cache container..."
    
    podman run -d \
        --pod "$POD_NAME" \
        --name "$REDIS_NAME" \
        --volume redis_data:/data:Z \
        --restart unless-stopped \
        docker.io/redis:7-alpine \
        redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    
    # Wait for Redis to be ready
    print_status "Waiting for Redis to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if podman exec "$REDIS_NAME" redis-cli ping &>/dev/null; then
            print_success "Redis is ready"
            break
        fi
        sleep 1
        ((attempt++))
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_warning "Redis may not be fully ready, but continuing..."
    fi
}

# Run main application container
run_app() {
    print_status "Starting STIG RAG application container..."
    
    # Copy STIG data to data directory
    if [ -f "stig_data.json" ]; then
        cp -f "stig_data.json" "$DATA_DIR/"
        print_success "STIG data file copied to $DATA_DIR"
    fi
    
    podman run -d \
        --pod "$POD_NAME" \
        --name "$APP_NAME" \
        --volume "$DATA_DIR:/app/data:ro,Z" \
        --volume "$CACHE_DIR:/app/cache:Z" \
        --volume "$LOG_DIR:/app/logs:Z" \
        --env REDIS_HOST=localhost \
        --env LOG_LEVEL="${LOG_LEVEL:-INFO}" \
        --env APP_PORT=8000 \
        --restart unless-stopped \
        --memory="${MEMORY_LIMIT:-2g}" \
        --cpus="${CPU_LIMIT:-2}" \
        "$IMAGE_NAME"
    
    print_success "Application container started"
}

# Setup systemd service
setup_systemd() {
    print_status "Setting up systemd service..."
    
    # Create systemd user directory if it doesn't exist
    mkdir -p ~/.config/systemd/user/
    
    # Create service file
    cat > ~/.config/systemd/user/stig-rag.service << EOF
[Unit]
Description=RHEL STIG RAG Service
After=network-online.target
Wants=network-online.target

[Service]
Type=exec
ExecStart=/usr/bin/podman pod start $POD_NAME
ExecStop=/usr/bin/podman pod stop $POD_NAME
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
EOF

    # Reload systemd
    systemctl --user daemon-reload
    
    # Enable service
    systemctl --user enable stig-rag.service
    
    print_success "Systemd service configured"
}

# Health check
health_check() {
    print_status "Performing health check..."
    
    # Wait for application to start
    sleep 5
    
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -s "http://localhost:${PORT}/health" > /dev/null; then
            print_success "Application is healthy"
            
            # Get health status
            local health_status=$(curl -s "http://localhost:${PORT}/health")
            echo -e "${GREEN}Health Status:${NC} $health_status"
            break
        fi
        sleep 2
        ((attempt++))
        echo -n "."
    done
    
    if [ $attempt -eq $max_attempts ]; then
        print_error "Health check failed - application may not be running correctly"
        echo "Check logs with: podman logs $APP_NAME"
        exit 1
    fi
}

# Display access information
display_info() {
    echo
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}       RHEL STIG RAG Deployment Complete! 🚀${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo
    echo -e "${BLUE}Access Points:${NC}"
    echo -e "  • Web Interface:    ${GREEN}http://localhost:${PORT}${NC}"
    echo -e "  • API Documentation: ${GREEN}http://localhost:${PORT}/docs${NC}"
    echo -e "  • Health Check:     ${GREEN}http://localhost:${PORT}/health${NC}"
    echo -e "  • API Metrics:      ${GREEN}http://localhost:${PORT}/api/metrics${NC}"
    echo
    echo -e "${BLUE}Container Management:${NC}"
    echo -e "  • View logs:        ${YELLOW}podman logs $APP_NAME${NC}"
    echo -e "  • View Redis logs:  ${YELLOW}podman logs $REDIS_NAME${NC}"
    echo -e "  • Stop containers:  ${YELLOW}podman pod stop $POD_NAME${NC}"
    echo -e "  • Start containers: ${YELLOW}podman pod start $POD_NAME${NC}"
    echo -e "  • Remove all:       ${YELLOW}podman pod rm -f $POD_NAME${NC}"
    echo
    echo -e "${BLUE}Data Locations:${NC}"
    echo -e "  • STIG Data:  ${DATA_DIR}"
    echo -e "  • Cache:      ${CACHE_DIR}"
    echo -e "  • Logs:       ${LOG_DIR}"
    echo
    echo -e "${BLUE}Quick Test:${NC}"
    echo -e "  ${YELLOW}curl -X POST http://localhost:${PORT}/api/query \\${NC}"
    echo -e "  ${YELLOW}  -H \"Content-Type: application/json\" \\${NC}"
    echo -e "  ${YELLOW}  -d '{\"question\": \"How to configure SELinux?\"}'${NC}"
    echo
}

# Main deployment function
main() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}       RHEL STIG RAG Optimized Deployment Script${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --port)
                PORT="$2"
                shift 2
                ;;
            --no-redis)
                NO_REDIS=true
                shift
                ;;
            --no-systemd)
                NO_SYSTEMD=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --port PORT       Set the application port (default: 8000)"
                echo "  --no-redis        Skip Redis deployment"
                echo "  --no-systemd      Skip systemd service setup"
                echo "  --help            Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Run deployment steps
    check_prerequisites
    create_directories
    stop_existing
    build_image
    create_pod
    
    if [ "$NO_REDIS" != "true" ]; then
        run_redis
    else
        print_warning "Skipping Redis deployment (caching will be disabled)"
    fi
    
    run_app
    
    if [ "$NO_SYSTEMD" != "true" ]; then
        setup_systemd
    fi
    
    health_check
    display_info
    
    print_success "Deployment completed successfully!"
}

# Run main function
main "$@"
