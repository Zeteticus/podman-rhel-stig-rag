#!/bin/bash
# STIG RAG Management Script

CONTAINER_NAME="stig-rag-textsearch"
IMAGE_NAME="localhost/rhel-stig-rag:textsearch"
PORT="8000"

case "$1" in
    start)
        echo "Starting STIG RAG..."
        ./deploy.sh
        ;;
    stop)
        echo "Stopping STIG RAG..."
        podman stop $CONTAINER_NAME
        ;;
    restart)
        echo "Restarting STIG RAG..."
        podman restart $CONTAINER_NAME
        ;;
    status)
        echo "STIG RAG Status:"
        podman ps --filter name=$CONTAINER_NAME
        ;;
    logs)
        echo "STIG RAG Logs:"
        podman logs --tail 20 $CONTAINER_NAME
        ;;
    clean)
        echo "Cleaning up old containers and images..."
        podman stop $CONTAINER_NAME 2>/dev/null || true
        podman rm $CONTAINER_NAME 2>/dev/null || true
        podman rmi $IMAGE_NAME 2>/dev/null || true
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|clean}"
        echo ""
        echo "Commands:"
        echo "  start   - Deploy and start STIG RAG"
        echo "  stop    - Stop STIG RAG"
        echo "  restart - Restart STIG RAG"
        echo "  status  - Show container status"
        echo "  logs    - Show recent logs"
        echo "  clean   - Remove containers and images"
        exit 1
        ;;
esac
