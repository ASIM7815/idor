# The Leaky Invoice - IDOR CTF Challenge

A beginner-friendly Capture The Flag (CTF) challenge demonstrating **Broken Object-Level Authorization (BOLA)**, also known as **Insecure Direct Object Reference (IDOR)**.

## 🎯 Challenge Overview

Participants log in as a normal user and must discover a legacy invoice viewer that lacks proper authorization checks, allowing them to access invoices belonging to other users and retrieve the hidden flag.

**Learning Objectives:**
- Understanding authorization vs authentication
- Identifying IDOR vulnerabilities
- Recognizing the importance of access control checks
- Understanding that predictable IDs are not the root cause (missing authorization is)

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# 1. Set up environment
cp .env.example .env
# Edit .env and set LEAKY_INVOICE_FLAG and LEAKY_INVOICE_SECRET_KEY

# 2. Start the application
make run

# 3. Access at http://localhost:5000
# Login: alice / password123
```

### Using Make Commands

```bash
make help      # Show available commands
make build     # Build Docker image
make run       # Start application
make logs      # View logs
make health    # Check health
make stop      # Stop application
make dev       # Run development server
```

## 📋 Requirements

**Production Deployment:**
- Docker & Docker Compose
- (Optional) Nginx for reverse proxy
- (Optional) SSL certificate for HTTPS

**Local Development:**
- Python 3.11+
- pip or venv

## 🔧 Configuration

### Environment Variables

Create a `.env` file based on `.env.example`:

```bash
# Required: Your CTF flag
LEAKY_INVOICE_FLAG=FLAG{your_unique_flag_here}

# Required: Flask secret key (generate with: python3 -c "import secrets; print(secrets.token_hex(32))")
LEAKY_INVOICE_SECRET_KEY=your_secret_key_here

# Optional: Database path
LEAKY_INVOICE_DATABASE=/data/leaky_invoices.db

# Optional: Environment
FLASK_ENV=production
```

**Security**: Never commit `.env` with real values to version control!

## 🎮 Demo Accounts

| Username | Password | Purpose |
|----------|----------|---------|
| alice | password123 | Participant account (public) |
| bob | *secret* | Target account with flag (private) |

## 🏗️ Production Features

This CTF challenge includes production-ready features:

- ✅ **Security Hardening**: Rate limiting, security headers, input validation
- ✅ **Docker Support**: Multi-stage builds, non-root user, health checks
- ✅ **Monitoring**: Health check endpoints, structured logging
- ✅ **Error Handling**: Custom error pages, graceful degradation
- ✅ **Session Security**: Secure, httponly, samesite cookies
- ✅ **HTTPS Support**: Talisman integration, Nginx configuration example
- ✅ **Database Management**: Automatic migrations, backup utilities

## 📖 Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Comprehensive production deployment guide
- **[nginx.conf.example](nginx.conf.example)** - Nginx reverse proxy configuration
- **[.env.example](.env.example)** - Environment variable template

## 🧪 Testing

### Smoke Tests
```bash
make test
```

### Manual Testing
```bash
# Check health
curl http://localhost:5000/health

# Test endpoints
curl http://localhost:5000/robots.txt
curl http://localhost:5000/
```

### Vulnerability Testing
1. Login as alice (alice/password123)
2. Explore the application
3. Check notifications and legacy tools
4. Find the legacy invoice viewer
5. Attempt to access Bob's invoices via legacy references

## 🎓 Educational Use

### For CTF Organizers:
- Deploy with unique flags per event
- Monitor for brute force attempts
- Provide hints if participants get stuck
- Reset database between events

### For Learners:
- Understand the difference between authentication and authorization
- Learn to identify missing access control checks
- Practice discovering hidden endpoints
- Understand IDOR vulnerability patterns

### Intentional Vulnerability:
The application contains an **intentional IDOR vulnerability** in the legacy invoice viewer (`/legacy/invoice/<legacy_ref>`). This route:
- ✅ Checks if the user is authenticated
- ❌ Does NOT check if the user owns the requested invoice
- ✅ All other routes properly validate ownership

This demonstrates how a single missing authorization check can compromise security.

## 🛠️ Development

### Local Development Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export LEAKY_INVOICE_SECRET_KEY="dev-secret-key"
echo "FLAG{dev_flag}" > .flag

# Run development server
python app.py
```

### Project Structure

```
├── app.py                    # Main Flask application
├── templates/                # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── invoice.html
│   ├── legacy_invoice.html   # Vulnerable endpoint
│   └── error.html
├── static/
│   └── style.css
├── Dockerfile                # Production Docker image
├── docker-compose.yml        # Docker Compose configuration
├── start.sh                  # Production startup script
├── requirements.txt          # Python dependencies
├── nginx.conf.example        # Nginx configuration
├── DEPLOYMENT.md             # Deployment documentation
└── Makefile                  # Common commands
```

## 🔒 Security Considerations

### Implemented Security Measures:
- Rate limiting (10 login attempts/minute, 200 requests/hour)
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Input validation and sanitization
- Secure session management
- SQL injection protection (parameterized queries)
- Password hashing (Werkzeug security)
- Non-root Docker container
- Error handling without information disclosure

### Intentional Vulnerability:
The legacy invoice viewer lacks authorization checks for educational purposes. This is the only intentional vulnerability - all other security measures are production-grade.

## 📊 Monitoring

### Health Check
```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### View Logs
```bash
make logs

# Or directly with docker
docker logs -f leaky-invoice
```

## 🤝 Contributing

This is an educational project. If you find bugs (other than the intentional IDOR vulnerability) or have suggestions for improvement, please open an issue.

## ⚠️ Disclaimer

This application contains intentional security vulnerabilities for educational purposes. **DO NOT** use this code in production systems or as a template for real applications without removing the intentional vulnerabilities and conducting a thorough security audit.

## 📜 License

Educational use only. The flag and challenge content should not be distributed publicly during active CTF events.

## 🎯 Challenge Solution

<details>
<summary>Click to reveal solution (spoiler!)</summary>

### Steps to solve:
1. Login as alice with password123
2. Navigate to the notifications page
3. Read about the legacy invoice viewer
4. Access `/legacy-tools` or follow the link from notifications
5. Try the legacy invoice viewer at `/legacy/invoice/`
6. Notice it uses different identifiers (legacy references)
7. Enumerate or guess legacy references to find Bob's invoices
8. Access Bob's private invoice (INV-2024-B2) containing the flag

### The Vulnerability:
The route `/legacy/invoice/<legacy_ref>` authenticates the user but never checks if the invoice belongs to them:

```python
@app.route('/legacy/invoice/<legacy_ref>')
def legacy_invoice_detail(legacy_ref):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    invoice = get_invoice_by_legacy_id(legacy_ref)  # No owner check!
```

### The Fix:
Add authorization check:
```python
if invoice['user_id'] != session['user_id']:
    flash(INVOICE_NOT_FOUND_MESSAGE, 'error')
    return redirect(url_for('dashboard'))
```

</details>

---

**Happy Hacking! 🏴‍☠️**
