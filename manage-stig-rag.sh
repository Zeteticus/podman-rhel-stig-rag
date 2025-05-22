#!/bin/bash
# Management script for RHEL STIG RAG Podman deployment

set -e

# Configuration
CONTAINER_NAME="stig-rag"
POD_NAME="stig-rag-pod"
IMAGE_NAME="localhost/rhel-stig-rag:latest"
HOST_PORT="8000"
DATA_DIR="$HOME/stig-rag-data"
LOG_DIR="$HOME/stig-rag-logs"
CONFIG_DIR="$HOME/stig-rag-config"
SYSTEMD_USER=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
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
    echo "RHEL STIG RAG Podman Management Script"
    echo "Usage: $0 COMMAND [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  status           Show service and container status"
    echo "  logs [OPTS]      Show container logs (use -f to follow)"
    echo "  start            Start services"
    echo "  stop             Stop services"
    echo "  restart          Restart services"
    echo "  update           Update container with latest image"
    echo "  backup           Run a manual backup"
    echo "  shell            Open a shell in the container"
    echo "  health           Check container and service health"
    echo "  cleanup          Clean up stopped containers and unused images"
    echo "  help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 logs -f       # Follow logs in real-time"
    echo "  $0 health        # Run health checks"
    echo "  $0 shell         # Open interactive shell"
}

get_podman_cmd() {
    if command -v podman &>/dev/null; then
        echo "podman"
    else
        print_error "Podman not found. Please install Podman."
        exit 1
    fi
}

get_systemctl_cmd() {
    if [ "$SYSTEMD_USER" = true ]; then
        echo "systemctl --user"
    else
        echo "sudo systemctl"
    fi
}

check_container_exists() {
    local podman_cmd=$(get_podman_cmd)
    
    if ! $podman_cmd container exists "$CONTAINER_NAME" 2>/dev/null; then
        print_error "Container '$CONTAINER_NAME' not found."
        print_error "Run deploy-podman.sh first to set up the container."
        exit 1
    fi
}

check_pod_exists() {
    local podman_cmd=$(get_podman_cmd)
    
    if ! $podman_cmd pod exists "$POD_NAME" 2>/dev/null; then
        print_error "Pod '$POD_NAME' not found."
        print_error "Run deploy-podman.sh first to set up the pod."
        exit 1
    fi
}

status() {
    local podman_cmd=$(get_podman_cmd)
    local systemctl_cmd=$(get_systemctl_cmd)
    
    print_status "RHEL STIG RAG System Status"
    echo
    
    # Check systemd service status
    echo -e "${BLUE}Systemd Service Status:${NC}"
    $systemctl_cmd status "$POD_NAME.service" --no-pager 2>/dev/null || 
        echo "Service not found or not managed by systemd"
    echo
    
    # Check pod status
    echo -e "${BLUE}Pod Status:${NC}"
    $podman_cmd pod ps --filter "name=$POD_NAME" || echo "Pod not found"
    echo
    
    # Check container status
    echo -e "${BLUE}Container Status:${NC}"
    $podman_cmd ps --filter "name=$CONTAINER_NAME" || echo "Container not found"
    echo
    
    # Check health
    echo -e "${BLUE}Health Check:${NC}"
    if $podman_cmd container exists "$CONTAINER_NAME" 2>/dev/null; then
        if $podman_cmd healthcheck run "$CONTAINER_NAME" &>/dev/null; then
            echo "Container health check: HEALTHY"
        else
            echo "Container health check: UNHEALTHY"
        fi
    else
        echo "Container health check: N/A (container not found)"
    fi
    
    # Check API
    if curl -s -f "http://localhost:$HOST_PORT/health" &>/dev/null; then
        echo "API health check: HEALTHY"
        echo "Service URL: http://localhost:$HOST_PORT"
    else
        echo "API health check: UNHEALTHY or NOT RUNNING"
    fi
    echo
    
    # Resource usage
    echo -e "${BLUE}Resource Usage:${NC}"
    $podman_cmd stats --no-stream "$CONTAINER_NAME" 2>/dev/null || 
        echo "Resource statistics not available"
}

show_logs() {
    local podman_cmd=$(get_podman_cmd)
    check_container_exists
    
    print_status "Container logs for $CONTAINER_NAME:"
    echo
    
    $podman_cmd logs "$@" "$CONTAINER_NAME"
}

start_services() {
    local systemctl_cmd=$(get_systemctl_cmd)
    local podman_cmd=$(get_podman_cmd)
    
    print_status "Starting RHEL STIG RAG services..."
    
    # Try systemd service first
    if $systemctl_cmd is-enabled "$POD_NAME.service" &>/dev/null; then
        $systemctl_cmd start "$POD_NAME.service"
        print_status "Service started via systemd"
    # Fall back to podman commands
    elif $podman_cmd pod exists "$POD_NAME" 2>/dev/null; then
        $podman_cmd pod start "$POD_NAME"
        print_status "Pod started via podman"
    else
        print_error "Services not found. Run deploy-podman.sh first."
        exit 1
    fi
    
    # Wait for service to be ready
    print_status "Waiting for service to be ready..."
    for i in {1..30}; do
        if curl -s -f "http://localhost:$HOST_PORT/health" &>/dev/null; then
            print_status "Service is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
    done
    
    print_warning "Service started but health check timed out."
    print_warning "Check logs for details: $0 logs"
}

stop_services() {
    local systemctl_cmd=$(get_systemctl_cmd)
    local podman_cmd=$(get_podman_cmd)
    
    print_status "Stopping RHEL STIG RAG services..."
    
    # Try systemd service first
    if $systemctl_cmd is-active "$POD_NAME.service" &>/dev/null; then
        $systemctl_cmd stop "$POD_NAME.service"
        print_status "Service stopped via systemd"
    # Fall back to podman commands
    elif $podman_cmd pod exists "$POD_NAME" 2>/dev/null; then
        $podman_cmd pod stop "$POD_NAME"
        print_status "Pod stopped via podman"
    else
        print_error "Services not found. Nothing to stop."
        exit 1
    fi
}

restart_services() {
    stop_services
    sleep 2
    start_services
}

update_container() {
    local podman_cmd=$(get_podman_cmd)
    
    print_status "Updating RHEL STIG RAG container..."
    
    # Build new image
    if [ -f "./Containerfile" ]; then
        print_status "Building new image from Containerfile..."
        $podman_cmd build -t "$IMAGE_NAME" .
    else
        print_warning "Containerfile not found. Pulling image instead..."
        $podman_cmd pull "$IMAGE_NAME"
    fi
    
    # Stop running container
    stop_services
    
    # Remove existing container
    if $podman_cmd container exists "$CONTAINER_NAME" 2>/dev/null; then
        $podman_cmd rm "$CONTAINER_NAME"
    fi
    
    # Create new container with same parameters
    print_status "Recreating container with updated image..."
    $podman_cmd run -d \
        --name "$CONTAINER_NAME" \
        --pod "$POD_NAME" \
        --env-file "$CONFIG_DIR/config.env" \
        --volume "$DATA_DIR/stig_data:/app/stig_data:Z" \
        --volume "$DATA_DIR/stig_chroma_db:/app/stig_chroma_db:Z" \
        --volume "$LOG_DIR:/app/logs:Z" \
        --restart unless-stopped \
        "$IMAGE_NAME"
    
    # Start service
    start_services
    
    print_status "Container updated successfully!"
}

backup_data() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_dir="$HOME/stig-rag-backups"
    local backup_file="$backup_dir/stig-rag-backup-$timestamp.tar.gz"
    
    print_status "Creating backup of STIG RAG data..."
    
    # Create backup directory if it doesn't exist
    mkdir -p "$backup_dir"
    
    # Create backup
    tar -czf "$backup_file" \
        -C "$DATA_DIR" \
        stig_data \
        stig_chroma_db
    
    print_status "Backup created: $backup_file"
    
    # Cleanup old backups (keep last 10)
    print_status "Cleaning up old backups..."
    ls -t "$backup_dir"/*.tar.gz 2>/dev/null | tail -n +11 | xargs rm -f 2>/dev/null || true
    
    print_status "Backup completed successfully!"
}

open_shell() {
    local podman_cmd=$(get_podman_cmd)
    check_container_exists
    
    print_status "Opening shell in $CONTAINER_NAME container..."
    $podman_cmd exec -it "$CONTAINER_NAME" /bin/bash
}

check_health() {
    local podman_cmd=$(get_podman_cmd)
    
    print_status "Running comprehensive health checks..."
    
    # Check if container exists
    if ! $podman_cmd container exists "$CONTAINER_NAME" 2>/dev/null; then
        print_error "Container '$CONTAINER_NAME' not found!"
        return 1
    fi
    
    # Check container status
    local state=$($podman_cmd inspect --format '{{.State.Status}}' "$CONTAINER_NAME")
    if [ "$state" != "running" ]; then
        print_error "Container is not running (status: $state)"
        return 1
    fi
    print_status "Container status: $state"
    
    # Check container health
    if $podman_cmd healthcheck run "$CONTAINER_NAME" &>/dev/null; then
        print_status "Container health check: PASSED"
    else
        print_warning "Container health check: FAILED"
    fi
    
    # Check API health
    if curl -s -f "http://localhost:$HOST_PORT/health" &>/dev/null; then
        print_status "API health check: PASSED"
        
        # Try a basic query
        local response=$(curl -s -X POST "http://localhost:$HOST_PORT/query" \
            -H "Content-Type: application/json" \
            -d '{"question": "Test query", "rhel_version": "9"}')
        
        if echo "$response" | grep -q "answer"; then
            print_status "API query test: PASSED"
        else
            print_warning "API query test: FAILED"
            print_warning "Response: $response"
        fi
    else
        print_error "API health check: FAILED (service not responding)"
    fi
    
    # Check resource usage
    print_status "Resource usage:"
    $podman_cmd stats --no-stream "$CONTAINER_NAME"
    
    print_status "Health check completed."
}

cleanup_resources() {
    local podman_cmd=$(get_podman_cmd)
    
    print_status "Cleaning up resources..."
    
    # Clean up stopped containers
    print_status "Removing stopped containers..."
    $podman_cmd container prune -f
    
    # Clean up unused images
    print_status "Removing unused images..."
    $podman_cmd image prune -f
    
    # Clean up unused volumes
    print_status "Removing unused volumes..."
    $podman_cmd volume prune -f
    
    print_status "Cleanup completed successfully!"
}

# Main execution
if [ $# -eq 0 ]; then
    usage
    exit 1
fi

case "$1" in
    status)
        status
        ;;
    logs)
        shift
        show_logs "$@"
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    update)
        update_container
        ;;
    backup)
        backup_data
        ;;
    shell)
        open_shell
        ;;
    health)
        check_health
        ;;
    cleanup)
        cleanup_resources
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac