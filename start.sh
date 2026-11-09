#!/bin/sh
set -eu

echo "=== The Leaky Invoice - Starting ==="

# Validate required environment variables
if [ -z "${LEAKY_INVOICE_FLAG:-}" ]; then
    echo "ERROR: LEAKY_INVOICE_FLAG environment variable is required"
    exit 1
fi

if [ -z "${LEAKY_INVOICE_SECRET_KEY:-}" ]; then
    echo "ERROR: LEAKY_INVOICE_SECRET_KEY environment variable is required"
    exit 1
fi

echo "Initializing database..."
python -c "import app; app.init_db()" || {
    echo "ERROR: Database initialization failed"
    exit 1
}

echo "Database initialized successfully"
echo "Starting Gunicorn server..."

# Production-ready Gunicorn configuration
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --worker-class sync \
    --timeout 30 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    app:app
