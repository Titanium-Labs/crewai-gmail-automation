# Gmail CrewAI Automation - Docker Deployment Guide

This guide explains how to run the Gmail CrewAI Automation server using Docker for easy deployment and management.

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- OpenAI API key
- Google OAuth2 credentials (optional, can be configured via web interface)

### 1. Clone and Setup

```bash
git clone <your-repo-url>
cd crewai-gmail-automation

# Copy environment template
cp docker-setup.env.example .env

# Edit .env with your configuration
nano .env  # or use your preferred editor
```

### 2. Configure Environment Variables

Edit `.env` file with your values:

```bash
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional OAuth2 (can be set via web interface)
GOOGLE_OAUTH_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret
OAUTH_REDIRECT_URI=http://localhost:8501
```

### 3. Start the Container

```bash
# Build and start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f gmail-crewai

# Check status
docker-compose ps
```

### 4. Access the Application

Open your browser and navigate to:
- **Local development**: http://localhost:8501
- **Production**: Replace localhost with your server IP/domain

## 📋 Configuration Options

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI processing | `sk-...` |

### Optional OAuth2 Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_OAUTH_CLIENT_ID` | Google OAuth Client ID | None |
| `GOOGLE_OAUTH_CLIENT_SECRET` | Google OAuth Client Secret | None |
| `OAUTH_REDIRECT_URI` | OAuth redirect URI | `http://localhost:8501` |

### Application Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging level | `INFO` |
| `EMAIL_ADDRESS` | Gmail address (for IMAP) | None |
| `APP_PASSWORD` | Gmail app password | None |

### Billing Configuration (Optional)

| Variable | Description |
|----------|-------------|
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key |
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook secret |

## 🛠️ Docker Commands

### Basic Operations

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View logs
docker-compose logs -f

# Access container shell
docker-compose exec gmail-crewai bash
```

### Data Management

```bash
# Backup data volumes
docker run --rm -v gmail_tokens:/data -v $(pwd):/backup alpine tar czf /backup/gmail-data-backup.tar.gz /data

# Restore data volumes
docker run --rm -v gmail_tokens:/data -v $(pwd):/backup alpine tar xzf /backup/gmail-data-backup.tar.gz -C /

# View volume information
docker volume ls
docker volume inspect gmail_tokens
```

### Container Maintenance

```bash
# Update container
docker-compose pull
docker-compose up -d

# Rebuild container
docker-compose build --no-cache
docker-compose up -d

# View resource usage
docker stats gmail-crewai-automation

# Check health status
docker-compose ps
```

## 📂 Data Persistence

The following data is persisted in Docker volumes:

- **`gmail_tokens`**: OAuth2 authentication tokens
- **`gmail_logs`**: Application logs
- **`gmail_output`**: Email processing outputs
- **`gmail_knowledge`**: User knowledge base

### Volume Locations

In the container, data is stored at:
- `/app/data/tokens/` - OAuth tokens
- `/app/data/logs/` - Application logs
- `/app/data/output/` - Processing results
- `/app/data/knowledge/` - Knowledge base

## 🔧 Troubleshooting

### Common Issues

**Container won't start:**
```bash
# Check logs for errors
docker-compose logs gmail-crewai

# Check if ports are available
netstat -tulpn | grep 8501
```

**OAuth2 authentication issues:**
```bash
# Check OAuth configuration
docker-compose exec gmail-crewai env | grep OAUTH

# Verify redirect URI matches your setup
curl -I http://localhost:8501
```

**Memory issues:**
```bash
# Check container resources
docker stats gmail-crewai-automation

# Increase memory limits in docker-compose.yml
```

### Health Checks

The container includes health checks:
```bash
# Check health status
docker-compose ps

# Manual health check
docker-compose exec gmail-crewai curl -f http://localhost:8501/_stcore/health
```

### Logs

View different types of logs:
```bash
# Container logs
docker-compose logs -f gmail-crewai

# Application logs (inside container)
docker-compose exec gmail-crewai tail -f /app/data/logs/*.log

# System logs
journalctl -u docker.service -f
```

## 🌐 Production Deployment

### Security Considerations

1. **Use HTTPS**: Set up a reverse proxy (nginx/traefik) with SSL
2. **Secure environment variables**: Use Docker secrets
3. **Network security**: Configure firewall rules
4. **Regular updates**: Keep container images updated

### Sample Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    location / {
        proxy_pass http://localhost:8501;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Streamlit
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Production Environment Variables

Update your `.env` for production:
```bash
OAUTH_REDIRECT_URI=https://your-domain.com
LOG_LEVEL=WARNING
```

## 🔄 Updates and Maintenance

### Updating the Application

```bash
# Pull latest images
docker-compose pull

# Recreate containers
docker-compose up -d

# Clean up old images
docker image prune -f
```

### Backup Strategy

```bash
#!/bin/bash
# backup-script.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/gmail-crewai"

mkdir -p $BACKUP_DIR

# Backup volumes
docker run --rm \
  -v gmail_tokens:/data/tokens \
  -v gmail_logs:/data/logs \
  -v gmail_output:/data/output \
  -v gmail_knowledge:/data/knowledge \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/gmail-crewai-$DATE.tar.gz /data

echo "Backup completed: gmail-crewai-$DATE.tar.gz"
```

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review container logs: `docker-compose logs -f`
3. Verify environment configuration
4. Check OAuth2 setup in Google Console

## 📝 Development

To run in development mode with live code changes:

```bash
# Use development override
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Create `docker-compose.dev.yml`:
```yaml
version: '3.8'
services:
  gmail-crewai:
    volumes:
      - .:/app
    environment:
      - LOG_LEVEL=DEBUG
``` 