# Alquiler

> Rental management SaaS platform built for the Nigerian (NGN) market.

Alquiler is a Django 5.2 + DRF backend with a React frontend for managing properties, tenants, leases, and rent collection. It serves three user roles: Landlord, Tenant, and Platform Admin.

## Features

- **Property Management** — Create properties, manage units, track occupancy
- **Tenant Management** — Invite tenants, manage profiles, view history
- **Lease Lifecycle** — Create, renew, terminate leases with overlap detection
- **Rent Collection** — Record payments, generate rent schedules, track overdue rent
- **Notifications** — 15 notification types with idempotent generation and email support
- **Subscriptions** — 3-tier SaaS billing (Free, Professional, Business) with trial management
- **Analytics Dashboard** — Landlord, Tenant, and Admin dashboards with KPIs and CSV exports
- **Platform Admin Console** — User management, property oversight, operational issues tracking

## Tech Stack

### Backend

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Framework | Django 5.2 |
| API | Django REST Framework 3.15+ |
| Auth | Token-based (DRF TokenAuthentication) |
| Database | PostgreSQL 16 (SQLite for dev) |
| Cache | Redis 7 |
| HTTP Server | Gunicorn |
| Container | Docker + Docker Compose |

### Frontend

| Component | Technology |
|-----------|------------|
| Framework | React 19 |
| Language | TypeScript 6 |
| Bundler | Vite 8 |
| Styling | Tailwind CSS 4 |
| Charts | Recharts 2 |
| Testing | Vitest + Testing Library |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16
- Redis 7
- Docker & Docker Compose (optional)

### Backend Setup

```bash
# Clone the repository
git clone <repository-url>
cd Alquiler

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
copy .env.example .env
# Edit .env with your database credentials

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Docker Setup

```bash
# Build and start all services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser
```

## API Documentation

Once the server is running, access the API documentation:

- **Swagger UI:** `http://localhost:8000/api/docs/`
- **ReDoc:** `http://localhost:8000/api/redoc/`
- **Schema:** `http://localhost:8000/api/schema/`

### Key Endpoints

| Group | Endpoints | Auth Required |
|-------|-----------|---------------|
| Auth | 8 | Mixed |
| Properties | 5 | Landlord/Admin |
| Tenants | 5 | Landlord/Tenant |
| Leases | 6 | Landlord/Tenant |
| Payments | 6 | Landlord/Tenant |
| Notifications | 6 | Own only |
| Subscriptions | 7 | Landlord/Admin |
| Dashboard | 5 | Role-gated |
| Health | 1 | None |

## Project Structure

```
Alquiler/
├── backend/
│   ├── config/              # Settings and URL routing
│   ├── core/                # Auth, user model, permissions
│   ├── properties/          # Property and unit management
│   ├── tenants/             # Tenant invitations and profiles
│   ├── leases/              # Lease lifecycle management
│   ├── payments/            # Payment recording and rent tracking
│   ├── notifications/       # Notification generation
│   ├── subscriptions/       # SaaS billing and plan management
│   ├── dashboard/           # Analytics and CSV exports
│   └── platform_admin/      # Platform operations console
├── frontend/
│   └── src/
│       ├── api/             # API client layer
│       ├── components/      # Reusable UI components
│       ├── contexts/        # React contexts
│       └── pages/           # Page components
├── docker-compose.yml
└── requirements.txt
```

## Development

### Running Tests

```bash
# Backend tests
python manage.py test

# Frontend tests
cd frontend
npm run test
```

### Linting

```bash
# Frontend
cd frontend
npm run lint
```

## Deployment

### Environment Variables

Key environment variables to configure:

```env
# Database
DB_NAME=alquiler
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Django
SECRET_KEY=your-secret-key
DEBUG=False
ALLOWED_HOSTS=your-domain.com

# Redis
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ALLOWED_ORIGINS=https://your-domain.com
```

### Production

```bash
# Build Docker images
docker-compose -f docker-compose.prod.yml build

# Start services
docker-compose -f docker-compose.prod.yml up -d

# Collect static files
docker-compose -f docker-compose.prod.yml exec web python manage.py collectstatic
```

## License

[Add your license here]
