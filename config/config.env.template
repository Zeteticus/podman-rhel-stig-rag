# RHEL STIG RAG - Podman Deployment Configuration
# Copy this file to config.env and customize settings as needed

#----------------------------------------
# Basic Application Settings
#----------------------------------------
APP_NAME=RHEL STIG RAG Assistant
APP_VERSION=1.0.0
APP_HOST=0.0.0.0
APP_PORT=8000

#----------------------------------------
# RHEL Version Priority
#----------------------------------------
DEFAULT_RHEL_VERSION=9
SUPPORTED_RHEL_VERSIONS=8,9

#----------------------------------------
# Directory Paths (inside container)
#----------------------------------------
STIG_DATA_DIR=/app/stig_data
VECTORSTORE_PATH=/app/stig_chroma_db
LOG_DIR=/app/logs

#----------------------------------------
# Vector Store Settings
#----------------------------------------
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

#----------------------------------------
# Language Model Settings
#----------------------------------------
LLM_PROVIDER=huggingface
LLM_MODEL=microsoft/DialoGPT-medium
LLM_TEMPERATURE=0.1
LLM_MAX_LENGTH=2048

# Optional: OpenAI API (uncomment and set values if using OpenAI)
#OPENAI_API_KEY=your_key_here
#OPENAI_MODEL=gpt-3.5-turbo

# Optional: Anthropic API (uncomment and set values if using Anthropic)
#ANTHROPIC_API_KEY=your_key_here
#ANTHROPIC_MODEL=claude-3-sonnet-20240229

#----------------------------------------
# Search Settings
#----------------------------------------
DEFAULT_SEARCH_RESULTS=5
MAX_SEARCH_RESULTS=20
PREFER_RHEL9_RESULTS=true

#----------------------------------------
# Performance & Resource Settings
#----------------------------------------
# Caching
ENABLE_CACHING=true
CACHE_TTL_SECONDS=3600

# Resource optimizations
MALLOC_ARENA_MAX=2
OMP_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1

#----------------------------------------
# Logging Settings
#----------------------------------------
LOG_LEVEL=INFO
LOG_FORMAT=json

#----------------------------------------
# Security Settings
#----------------------------------------
ALLOWED_FILE_EXTENSIONS=.xml,.json,.txt
MAX_FILE_SIZE_MB=50
ENABLE_CORS=true
ALLOWED_ORIGINS=*

#----------------------------------------
# Podman & Container-Specific Settings
#----------------------------------------
# Set to true to enable cgroups compatibility mode
ENABLE_CGROUPS_COMPAT=true

# Cgroup manager: systemd or cgroupfs
CGROUP_MANAGER=systemd

# Health check parameters
HEALTH_CHECK_INTERVAL=30s
HEALTH_CHECK_TIMEOUT=10s
HEALTH_CHECK_RETRIES=3