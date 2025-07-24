#!/bin/bash

# Gmail CrewAI Automation - Docker Quick Start Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        echo "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi

    print_success "Docker and Docker Compose are installed"
}

# Setup environment file
setup_env() {
    if [[ ! -f .env ]]; then
        if [[ -f docker-setup.env.example ]]; then
            print_status "Creating .env file from template..."
            cp docker-setup.env.example .env
            print_warning "Please edit .env file with your configuration before proceeding"
            echo "Required: OPENAI_API_KEY"
            echo "Optional: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET"
            
            read -p "Do you want to edit .env now? (y/N): " edit_env
            if [[ $edit_env =~ ^[Yy]$ ]]; then
                ${EDITOR:-nano} .env
            fi
        else
            print_error "Environment template file not found!"
            exit 1
        fi
    else
        print_success ".env file already exists"
    fi
}

# Check environment variables
check_env() {
    if [[ ! -f .env ]]; then
        print_error ".env file not found!"
        exit 1
    fi

    source .env

    if [[ -z "$OPENAI_API_KEY" || "$OPENAI_API_KEY" == "your_openai_api_key_here" ]]; then
        print_error "OPENAI_API_KEY is not set in .env file"
        print_warning "Please edit .env and set your OpenAI API key"
        exit 1
    fi

    print_success "Environment configuration looks good"
}

# Build and start containers
start_containers() {
    print_status "Building and starting Gmail CrewAI containers..."
    
    # Stop any existing containers
    docker-compose down 2>/dev/null || true
    
    # Build and start
    if docker-compose up -d --build; then
        print_success "Containers started successfully!"
    else
        print_error "Failed to start containers"
        print_status "Checking logs..."
        docker-compose logs
        exit 1
    fi
}

# Wait for container to be healthy
wait_for_health() {
    print_status "Waiting for container to be healthy..."
    
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if docker-compose ps | grep -q "healthy"; then
            print_success "Container is healthy!"
            return 0
        fi
        
        if docker-compose ps | grep -q "unhealthy"; then
            print_error "Container is unhealthy"
            print_status "Checking logs..."
            docker-compose logs --tail=20
            exit 1
        fi
        
        ((attempt++))
        echo -n "."
        sleep 2
    done
    
    print_warning "Health check timeout, but container may still be starting..."
}

# Display access information
show_access_info() {
    echo ""
    echo "=================================================="
    echo "🎉 Gmail CrewAI Automation is now running!"
    echo "=================================================="
    echo ""
    echo "📱 Access the application:"
    echo "   Local:    http://localhost:8501"
    echo "   Network:  http://$(hostname -I | awk '{print $1}'):8501"
    echo ""
    echo "🔧 Useful commands:"
    echo "   View logs:        docker-compose logs -f"
    echo "   Stop:             docker-compose down"
    echo "   Restart:          docker-compose restart"
    echo "   Shell access:     docker-compose exec gmail-crewai bash"
    echo ""
    echo "📚 For more information, see DOCKER_README.md"
    echo ""
}

# Main function
main() {
    echo "🚀 Gmail CrewAI Automation - Docker Quick Start"
    echo "================================================"
    echo ""

    # Check prerequisites
    check_docker
    
    # Setup environment
    setup_env
    check_env
    
    # Start containers
    start_containers
    
    # Wait for health check
    wait_for_health
    
    # Show access information
    show_access_info
    
    # Option to view logs
    read -p "Do you want to view live logs? (y/N): " view_logs
    if [[ $view_logs =~ ^[Yy]$ ]]; then
        echo ""
        print_status "Showing live logs (Ctrl+C to exit)..."
        docker-compose logs -f
    fi
}

# Handle Ctrl+C
trap 'echo -e "\n\n👋 Setup interrupted. Containers may still be running."; exit 130' SIGINT

# Check if we're in the right directory
if [[ ! -f docker-compose.yml ]]; then
    print_error "docker-compose.yml not found!"
    print_status "Please run this script from the project root directory"
    exit 1
fi

# Run main function
main "$@" 