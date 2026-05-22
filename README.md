# Slash Backend

This is the backend repository for Slash, a Django-based web application providing REST APIs for product management, cart, orders, payments, reviews, and authentication.

## Prerequisites

Before setting up the project, ensure you have the following installed on your system:
- **Python** (3.10+ recommended)
- **Redis** (Required for Celery background tasks and caching)
- **Elasticsearch** (Required for search functionalities)
- **PostgreSQL** (Optional; the app defaults to SQLite if Postgres is not configured)

## Local Setup Instructions

1. **Clone the repository**
   ```bash
   git clone <repository_url>
   cd slash
   ```

2. **Set up a Virtual Environment**
   It is highly recommended to use a virtual environment to manage dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Configure Environment Variables**
   Copy the example environment file to `.env` and fill in the necessary credentials (like Database, Redis URLs, Elasticsearch, Google OAuth, and Flutterwave keys):
   ```bash
   cp .env.example .env
   ```

4. **Install Dependencies & Apply Migrations**
   The project includes a `Makefile` to simplify setup. The following command installs all dependencies from `requirements.txt` and runs the database migrations:
   ```bash
   make setup
   ```

5. **Create an Admin Superuser**
   To access the Django admin panel (`/admin/`), you will need a superuser account:
   ```bash
   make superuser
   ```

6. **Seed Initial Data (Optional)**
   Run the following command to create initial product categories in your database:
   ```bash
   make seed_categories
   ```

## Running the Application

Ensure that your local **Redis** and **Elasticsearch** services are running before starting the application.

You can run the Django development server, Celery worker, and Celery beat concurrently using the Makefile:

```bash
make dev
```

### Running Services Separately
If you prefer to run the services in separate terminal windows:
- **Django Server**: `make run` (or `python manage.py runserver`)
- **Celery Worker**: `make worker` (or `celery -A core worker -l info`)
- **Celery Beat**: `make beat` (or `celery -A core beat -l info`)

To stop all background services started via `make dev`:
```bash
make stop
```

## Useful Makefile Commands

- `make help` - View all available commands
- `make test` - Run the automated test suite
- `make shell` - Open the interactive Django shell
- `make clean` - Remove `.pyc` and `__pycache__` files

## Key Technologies & Integrations

- **Framework**: Django & Django REST Framework
- **API Documentation**: Generated via `drf-spectacular`
- **Authentication**: JWT authentication (`rest_framework_simplejwt`) and Social Login (`django-allauth` / Google OAuth)
- **Payments**: Flutterwave integration
- **Background Jobs**: Celery & Redis (handles tasks like scheduled payment processing and training recommendation models)
- **Admin Theme**: Unfold
