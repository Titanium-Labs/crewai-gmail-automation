#!/bin/bash
set -e

# Gmail CrewAI Docker Entrypoint Script
echo "🚀 Starting Gmail CrewAI Automation Server"

# Function to log messages
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Check for required environment variables
check_env_vars() {
    local required_vars=(
        "OPENAI_API_KEY"
    )
    
    local missing_vars=()
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        log "❌ Missing required environment variables:"
        printf '   - %s\n' "${missing_vars[@]}"
        log "Please set these variables and restart the container."
        exit 1
    fi
}

# Create necessary directories
setup_directories() {
    log "📁 Setting up data directories..."
    
    # Ensure data directories exist with proper permissions
    mkdir -p /app/data/{tokens,logs,output,knowledge}
    
    # Create default knowledge files if they don't exist
    if [[ ! -f /app/data/knowledge/user_facts.txt ]]; then
        cp -r /app/knowledge/* /app/data/knowledge/ 2>/dev/null || true
    fi
    
    log "✅ Data directories ready"
}

# Setup OAuth2 configuration
setup_oauth() {
    if [[ -n "$GOOGLE_OAUTH_CLIENT_ID" && -n "$GOOGLE_OAUTH_CLIENT_SECRET" ]]; then
        log "🔑 Setting up OAuth2 configuration..."
        
        # Create credentials.json from environment variables
        cat > /app/data/credentials.json << EOF
{
    "web": {
        "client_id": "$GOOGLE_OAUTH_CLIENT_ID",
        "client_secret": "$GOOGLE_OAUTH_CLIENT_SECRET",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "redirect_uris": ["${OAUTH_REDIRECT_URI:-http://localhost:8501}"]
    }
}
EOF
        
        # Set environment variable for the app
        export GOOGLE_APPLICATION_CREDENTIALS="/app/data/credentials.json"
        log "✅ OAuth2 credentials configured"
    else
        log "⚠️  OAuth2 environment variables not set. Manual setup will be required."
    fi
}

# Setup logging
setup_logging() {
    log "📋 Configuring logging..."
    
    # Set logging environment variables if not already set
    export LOG_LEVEL="${LOG_LEVEL:-INFO}"
    export LOG_FORMAT="${LOG_FORMAT:-%(asctime)s - %(name)s - %(levelname)s - %(message)s}"
    
    log "✅ Logging configured (Level: $LOG_LEVEL)"
}

# Display configuration
show_config() {
    log "⚙️  Container Configuration:"
    echo "   • Port: ${STREAMLIT_SERVER_PORT:-8501}"
    echo "   • Address: ${STREAMLIT_SERVER_ADDRESS:-0.0.0.0}"
    echo "   • Theme: ${STREAMLIT_THEME_BASE:-dark}"
    echo "   • Data Directory: /app/data"
    echo "   • OAuth Redirect: ${OAUTH_REDIRECT_URI:-http://localhost:8501}"
    echo "   • Log Level: ${LOG_LEVEL:-INFO}"
}

# Wait for dependencies (if any)
wait_for_dependencies() {
    # Add any dependency checks here (databases, external services)
    log "🔍 Checking dependencies..."
    
    # Example: Check if we can reach Gmail API
    if command -v curl >/dev/null 2>&1; then
        if curl -s --max-time 5 https://www.googleapis.com >/dev/null 2>&1; then
            log "✅ Gmail API reachable"
        else
            log "⚠️  Gmail API not reachable (may affect functionality)"
        fi
    fi
}

# Main initialization
main() {
    log "🔄 Initializing Gmail CrewAI container..."
    
    # Run initialization steps
    check_env_vars
    setup_directories
    setup_oauth
    setup_logging
    wait_for_dependencies
    show_config
    
    log "🎉 Initialization complete!"
    log "🌐 Starting Streamlit server on http://0.0.0.0:${STREAMLIT_SERVER_PORT:-8501}"
    
    # Execute the command passed to the container
    exec "$@"
}

# Handle signals for graceful shutdown
shutdown() {
    log "📴 Received shutdown signal, stopping gracefully..."
    # Add any cleanup tasks here
    exit 0
}

# Set up signal handlers
trap shutdown SIGTERM SIGINT

# Run main function
main "$@" 