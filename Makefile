.PHONY: help install migrate migrations superuser run worker beat dev shell test clean setup stop seed_categories

help:
	@echo "Available commands:"
	@echo "  setup        - Install dependencies and run migrations"
	@echo "  install      - Install dependencies"
	@echo "  migrate      - Run database migrations"
	@echo "  migrations   - Create new migrations"
	@echo "  superuser    - Create a Django superuser"
	@echo "  run          - Start the Django development server"
	@echo "  worker       - Start the Celery worker"
	@echo "  beat         - Start the Celery beat"
	@echo "  dev          - Start server and worker in parallel"
	@echo "  stop         - Stop server, worker, and beat"
	@echo "  seed_categories - Create initial product categories"
	@echo "  shell        - Open Django shell"
	@echo "  test         - Run tests"
	@echo "  clean        - Remove pyc files and __pycache__"

setup: install migrate migrations

install:
	pip install -r requirements.txt

migrate:
	python manage.py migrate

migrations:
	python manage.py makemigrations

superuser:
	python manage.py createsuperuser

run:
	python manage.py runserver

worker:
	celery -A core worker -l info

beat:
	celery -A core beat -l info

dev:
	@echo "Starting server, worker, and beat..."
	(trap 'kill 0' SIGINT; \
	 python manage.py runserver & \
	 celery -A core worker -l info & \
	 celery -A core beat -l info & \
	 wait)

stop:
	@echo "Stopping server, worker, and beat..."
	-pkill -f "manage.py runserver"
	-pkill -f "celery -A core"

shell:
	python manage.py shell

test:
	python manage.py test

seed_categories:
	python manage.py create_categories

clean:
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -delete
