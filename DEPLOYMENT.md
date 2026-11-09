# The Leaky Invoice — Production Deployment Guide

## Overview
This guide covers deploying The Leaky Invoice CTF challenge in a production environment with proper security hardening, monitoring, and reliability features.

## Production Features
- ✅ Multi-stage Docker build with non-root user
- ✅ Security headers (HSTS, CSP, X-Frame-Options)
- ✅ Rate limiting to prevent brute force attacks
- ✅ Structured logging
- ✅ Health check endpoints
- ✅ Graceful error handling
- ✅ Session security (httponly, secure, samesite cookies)
- ✅ Input validation
- ✅ Database connection pooling
- ✅ Automatic database migrations

## Requirements
- Docker & Docker Compose (recommended) OR
- Python 3.11+ with systemd (direct deployment)
- (Optional) Nginx for reverse proxy
- (Optional) SSL certificate for HTTPS

## Quick Start with Docker Compose

### 1. Configuration
Copy the environment template and configure:

```bash
cp .env.example .env
```

Edit `.env` and set:
```bash
# Generate a secure secret key
LEAKY_INVOICE_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Set your CTF flag
LEAKY_INVOICE_FLAG='FLAG{your_unique_flag_here}'

# Database path (inside container)
LEAKY_INVOICE_DATABASE=/data/leaky_invoices.db

# Environment
FLASK_ENV=production
```

**Security Warning**: Never commit `.env` with real values to version control!

### 2. Build and Run

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# Check logs
docker-compose logs -f

# Check health
curl http://localhost:5000/health
```

### 3. Access
- Application: http://localhost:5000
- Demo credentials: `alice` / `password123`

## Manual Docker Deployment

### Build
```bash
docker buildx build --load -t leaky-invoice:latest .
```

### Run with persistent storage
```bash
# Create volume for database
docker volume create leaky-invoice-data

# Run container
docker run -d \
  --name leaky-invoice \
  --restart unless-stopped \
  -p 5000:5000 \
  -v leaky-invoice-data:/data \
  -e LEAKY_INVOICE_DATABASE=/data/leaky_invoices.db \
  -e LEAKY_INVOICE_FLAG='FLAG{your_unique_flag_here}' \
  -e LEAKY_INVOICE_SECRET_KEY='your_long_random_secret_key' \
  -e FLASK_ENV=production \
  leaky-invoice:latest
```

## Production Deployment with Nginx

### 1. Configure Nginx
```bash
# Copy example configuration
sudo cp nginx.conf.example /etc/nginx/sites-available/leaky-invoice

# Edit the configuration
sudo nano /etc/nginx/sites-available/leaky-invoice
# Update: server_name, SSL certificate paths

# Enable site
sudo ln -s /etc/nginx/sites-available/leaky-invoice /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 2. Obtain SSL Certificate (Let's Encrypt)
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 3. Start Application
```bash
docker-compose up -d
```

## Environment Variables Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `LEAKY_INVOICE_FLAG` | Yes | CTF flag to be discovered | `FLAG{l3aky_1nv01c3s}` |
| `LEAKY_INVOICE_SECRET_KEY` | Yes | Flask session secret (64+ chars) | Generate with `secrets.token_hex(32)` |
| `LEAKY_INVOICE_DATABASE` | No | Database file path | `/data/leaky_invoices.db` |
| `FLASK_ENV` | No | Environment mode | `production` or `development` |

## Security Hardening Checklist

- [x] **Secret Management**: Use environment variables, never commit secrets
- [x] **Rate Limiting**: 10 attempts/min on login, 200 requests/hour globally
- [x] **Session Security**: Secure, httponly, samesite cookies
- [x] **Security Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- [x] **Input Validation**: Length limits, sanitization on all inputs
- [x] **HTTPS**: Force HTTPS in production (via Talisman + Nginx)
- [x] **Non-root Container**: Application runs as user `appuser` (UID 1000)
- [x] **Error Handling**: Custom error pages, no stack traces exposed
- [x] **Logging**: Structured logging without sensitive data
- [x] **Health Checks**: `/health` endpoint for monitoring

## Monitoring and Operations

### Health Check
```bash
curl http://localhost:5000/health

# Expected response:
# {"status":"healthy","database":"connected"}
```

### View Logs
```bash
# Docker Compose
docker-compose logs -f

# Docker
docker logs -f leaky-invoice

# Show last 100 lines
docker logs --tail 100 leaky-invoice
```

### Restart Service
```bash
# Docker Compose
docker-compose restart

# Docker
docker restart leaky-invoice
```

### Database Backup
```bash
# The application automatically creates backups before migrations
# Manual backup:
docker cp leaky-invoice:/data/leaky_invoices.db ./backup-$(date +%Y%m%d).db
```

### Update Application
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## Participant Access

### Provide to participants:
- **URL**: https://your-domain.com
- **Username**: `alice`
- **Password**: `password123`
- **Objective**: Find the vulnerability that allows accessing other users' invoices

### CTF Platform Integration
Add to your CTFd or other platform:
```markdown
**Challenge**: The Leaky Invoice
**Category**: Web Security
**Difficulty**: Beginner
**Points**: 100

Access the invoice management system and find Bob's private invoice.
The flag is hidden in the invoice description.

URL: https://your-domain.com
Username: alice
Password: password123
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker logs leaky-invoice

# Common issues:
# - Missing LEAKY_INVOICE_FLAG: Set in .env or docker run command
# - Missing LEAKY_INVOICE_SECRET_KEY: Set in .env or docker run command
# - Port 5000 in use: Change port mapping or stop conflicting service
```

### Database errors
```bash
# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d

# Or for manual deployment:
docker volume rm leaky-invoice-data
docker volume create leaky-invoice-data
docker restart leaky-invoice
```

### Rate limiting too aggressive
Adjust in `app.py`:
```python
limiter = Limiter(
    app=app,
    default_limits=["500 per hour"],  # Increase this
)
```

### Can't access from outside
- Check firewall rules
- Verify nginx configuration
- Ensure container is bound to 0.0.0.0 (for Docker) or use nginx proxy
- Check SSL certificate is valid

## Testing Before Event

### Pre-deployment checklist:
1. [ ] Login works with alice/password123
2. [ ] `/robots.txt` is accessible
3. [ ] `/legacy-tools` and `/legacy-tools/` both work
4. [ ] Dashboard shows Alice's invoices only
5. [ ] Current invoice viewer (via dashboard) shows ownership check working
6. [ ] Legacy invoice viewer is accessible via notifications or `/legacy/invoice/`
7. [ ] **IDOR vulnerability works**: Can access Bob's invoices via legacy viewer
8. [ ] Health check endpoint returns 200: `curl /health`
9. [ ] Rate limiting activates after 10 login attempts
10. [ ] SSL certificate is valid (if using HTTPS)
11. [ ] Logs are being written properly
12. [ ] Database persists after container restart

### Test the vulnerability:
```bash
# 1. Login as alice
# 2. Navigate to notifications or /legacy-tools
# 3. Find reference to legacy invoice viewer
# 4. Try accessing different legacy references
# 5. Should be able to view Bob's invoice: INV-2024-B2 containing the flag
```

## Security Note for Organizers

This application contains an **intentional IDOR vulnerability** in the legacy invoice viewer for educational purposes. The vulnerability allows authenticated users to access invoices belonging to other users by manipulating the legacy reference parameter.

**Do NOT**:
- Use this code in real production systems
- Expose the flag or Bob's credentials publicly
- Reuse the same flag across multiple events

**DO**:
- Generate a unique flag for each event
- Monitor for excessive requests or scanning
- Reset the database between events
- Keep organizer credentials (Bob's account) private

## Support and Maintenance

### Regular maintenance tasks:
- **Weekly**: Review logs for suspicious activity
- **Monthly**: Update dependencies (rebuild Docker image)
- **Per Event**: Reset database, generate new flag
- **After Event**: Archive database, rotate secrets

### Backup strategy:
```bash
# Before event
docker cp leaky-invoice:/data/leaky_invoices.db ./pre-event-backup.db

# After event
docker cp leaky-invoice:/data/leaky_invoices.db ./post-event-backup.db
```

## License and Attribution

The Leaky Invoice - A CTF Challenge for teaching Broken Object-Level Authorization (BOLA/IDOR)

Keep the flag, database, and organizer credentials private.
Do not distribute solutions before or during events.
