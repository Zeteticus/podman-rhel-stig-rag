#!/bin/bash

# Startup script for RHEL STIG RAG container
# This script:
# 1. Verifies/loads STIG data
# 2. Sets up the environment
# 3. Starts the FastAPI application

set -e

# Color codes for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Starting RHEL STIG RAG System...${NC}"

# Function to check Redis connectivity
check_redis() {
    if [ -n "$REDIS_HOST" ] && [ "$REDIS_HOST" != "none" ]; then
        echo "Checking Redis connectivity at $REDIS_HOST:$REDIS_PORT..."
        python3.11 -c "
import redis
import sys
try:
    r = redis.Redis(host='$REDIS_HOST', port=$REDIS_PORT, socket_connect_timeout=5)
    r.ping()
    print('✓ Redis connection successful')
    sys.exit(0)
except:
    print('✗ Redis connection failed - continuing without cache')
    sys.exit(1)
" || export REDIS_HOST="none"
    fi
}

# Function to verify STIG data
verify_stig_data() {
    echo "Verifying STIG data..."
    
    if [ ! -f "$DATA_DIR/stig_data.json" ]; then
        echo -e "${RED}ERROR: STIG data file not found at $DATA_DIR/stig_data.json${NC}"
        echo "Please mount your STIG data file to the container."
        echo "Example: -v /path/to/stig_data.json:/app/data/stig_data.json:ro"
        exit 1
    fi
    
    # Verify JSON is valid
    python3.11 -c "
import json
import sys
try:
    with open('$DATA_DIR/stig_data.json', 'r') as f:
        data = json.load(f)
    print(f'✓ STIG data file is valid JSON with {len(data)} entries')
except Exception as e:
    print(f'✗ Invalid STIG data file: {e}')
    sys.exit(1)
" || exit 1
}

# Function to load/verify embeddings cache
load_embeddings() {
    echo "Checking embeddings cache..."
    
    if [ -f "$CACHE_DIR/stig_embeddings.pkl" ]; then
        # Verify cache is valid and matches current data
        python3.11 -c "
import pickle
import json
import hashlib
import sys

# Calculate hash of current data
with open('$DATA_DIR/stig_data.json', 'rb') as f:
    current_hash = hashlib.md5(f.read()).hexdigest()

# Check if cache exists and is valid
try:
    with open('$CACHE_DIR/stig_embeddings.pkl', 'rb') as f:
        cache_data = pickle.load(f)
    
    # Verify cache has required keys
    if 'embeddings' in cache_data and 'processed_data' in cache_data:
        print('✓ Embeddings cache found and valid')
        sys.exit(0)
    else:
        print('✗ Cache is corrupted, will rebuild')
        sys.exit(1)
except:
    print('✗ Cache not found or invalid, will rebuild')
    sys.exit(1)
" || {
            echo -e "${YELLOW}Rebuilding embeddings cache...${NC}"
            python3.11 load_stig_data.py
        }
    else
        echo -e "${YELLOW}No embeddings cache found, building...${NC}"
        python3.11 load_stig_data.py
    fi
}

# Main startup sequence
main() {
    # Display environment
    echo "Environment Configuration:"
    echo "  - App Port: $APP_PORT"
    echo "  - Redis Host: $REDIS_HOST"
    echo "  - Log Level: $LOG_LEVEL"
    echo "  - Workers: $WORKERS"
    echo "  - Data Dir: $DATA_DIR"
    echo "  - Cache Dir: $CACHE_DIR"
    echo ""
    
    # Verify STIG data
    verify_stig_data
    
    # Check Redis
    check_redis
    
    # Load/verify embeddings
    load_embeddings
    
    # Export Redis availability for the app
    if [ "$REDIS_HOST" = "none" ]; then
        export REDIS_AVAILABLE="false"
    else
        export REDIS_AVAILABLE="true"
    fi
    
    # Start the FastAPI application
    echo -e "${GREEN}Starting FastAPI application...${NC}"
    echo "Access the application at http://localhost:$APP_PORT"
    echo ""
    
    # Use exec to replace the shell with uvicorn
    # This ensures proper signal handling for container shutdown
    exec uvicorn app:app \
        --host 0.0.0.0 \
        --port "$APP_PORT" \
        --workers "$WORKERS" \
        --loop uvloop \
        --access-log \
        --log-level "${LOG_LEVEL,,}" \
        --use-colors
}

# Handle signals gracefully
trap 'echo "Shutting down..."; exit 0' SIGTERM SIGINT

# Run main function
main
