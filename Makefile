.PHONY: help build run stop logs clean test health backup

help:
	@echo "The Leaky Invoice - Available commands:"
	@echo "  make build      - Build Docker image"
	@echo "  make run        - Start application with docker-compose"
	@echo "  make stop       - Stop application"
	@echo "  make logs       - View application logs"
	@echo "  make health     - Check application health"
	@echo "  make backup     - Backup database"
	@echo "  make clean      - Remove containers and volumes"
	@echo "  make test       - Run basic smoke tests"
	@echo "  make dev        - Run development server locally"

build:
	docker-compose build

run:
	docker-compose up -d
	@echo "Application started. Access at http://localhost:5000"
	@echo "Use 'make logs' to view logs"

stop:
	docker-compose down

logs:
	docker-compose logs -f

health:
	@echo "Checking application health..."
	@curl -s http://localhost:5000/health | python3 -m json.tool || echo "Health check failed"

backup:
	@mkdir -p backups
	@docker cp leaky-invoice:/data/leaky_invoices.db backups/leaky_invoices_$(shell date +%Y%m%d_%H%M%S).db
	@echo "Database backed up to backups/"

clean:
	docker-compose down -v
	@echo "Containers and volumes removed"

test:
	@echo "Running smoke tests..."
	@curl -s http://localhost:5000/health > /dev/null && echo "✓ Health check passed" || echo "✗ Health check failed"
	@curl -s http://localhost:5000/ > /dev/null && echo "✓ Home page accessible" || echo "✗ Home page failed"
	@curl -s http://localhost:5000/robots.txt | grep -q "legacy-tools" && echo "✓ Robots.txt present" || echo "✗ Robots.txt failed"

dev:
	@if [ ! -d "venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv venv; \
		./venv/bin/pip install -r requirements.txt; \
	fi
	@if [ ! -f ".flag" ]; then \
		echo "FLAG{dev_flag_12345}" > .flag; \
		echo "Created .flag file for development"; \
	fi
	@export LEAKY_INVOICE_SECRET_KEY="dev-secret-$$(date +%s)"; \
	./venv/bin/python app.py
