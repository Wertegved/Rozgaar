# Rozgaar

Rozgaar is a local work platform that helps Consumers publish jobs, compare Worker proposals, coordinate agreements, and track payments and completion in one clear workflow. It also gives Workers a practical way to discover work, apply with a proposed price, negotiate, manage availability, and track earnings without losing visibility into fair opportunity and scheduling.

## Problem being solved

Local service work often has friction between clear demand and trustworthy execution. Consumers need a way to describe work, compare realistic bids, and keep accountability through the lifecycle. Workers need a fair way to find relevant jobs, make sensible proposals, and stay informed about timing, payment, and completion. Rozgaar reduces ambiguity by keeping job details, proposals, agreements, payment milestones, and completion evidence in a single platform.

## Core differentiator

Rozgaar is not a generic marketplace. It emphasizes:

- clear local hiring workflow from job posting to completion
- explicit negotiation and agreement steps
- transparent payment milestones and completion evidence
- privacy-friendly communication and storage patterns
- location-aware intelligence for workers and administrators
- cooperative local labor coordination rather than anonymous gig arbitrage

## Separate websites

### Consumer website

The Consumer frontend focuses on posting work, reviewing applicants, accepting or rejecting proposals, paying advances, confirming completion, handling complaints, and tracking job progress.

### Worker website

The Worker frontend focuses on discovering jobs, applying with a proposal, negotiating, managing availability, tracking schedule and earnings, submitting completion evidence, and using regional opportunity intelligence.

### Cooperative/Admin website

The Admin frontend provides operational visibility into the platform, including job status, geographic demand/supply signals, heatmap-like regional intelligence, and oversight controls.

## Architecture

The repository is organized into separate frontend and backend concerns:

- consumer-web/: Consumer-facing static frontend
- worker-web/: Worker-facing static frontend
- admin-web/: Cooperative/Admin static frontend
- backend/: FastAPI backend, database models, services, APIs, tests
- docs/: design and architecture notes
- shared/: shared UI tokens/assets
- infra/: deployment scaffolding and infrastructure assets

## Technology stack actually used

- FastAPI for the API layer
- SQLAlchemy ORM with PostgreSQL database models
- Alembic for schema migrations
- Supabase PostgreSQL and Storage for managed hosted data services
- Supabase Realtime for authorized event delivery
- Redis for caching and Celery broker/result backend
- Celery for asynchronous task execution
- JWT-based authentication with RBAC
- Pydantic schemas and validation
- Static HTML/CSS/JS frontends served locally for demo flows
- Leaflet + OpenStreetMap for map-based geographic intelligence
- AI abstraction for provider-based model access

## FastAPI backend

The backend is built in Python with FastAPI and sits under the backend directory. It handles:

- user auth and registration
- role-based access control (CONSUMER, WORKER, ADMIN)
- jobs, applications, negotiations, agreements
- payments and simulated finalization flows
- completion evidence uploads and completion states
- notifications, reviews, complaints, and disputes
- geography and intelligence APIs

The application factory is defined in backend/app/main.py and the API router is mounted at /api/v1.

## PostgreSQL/Supabase

Rozgaar is designed around PostgreSQL-backed storage and Supabase-powered infrastructure. The project uses:

- PostgreSQL-compatible database access via SQLAlchemy
- Supabase-managed credential and secret handling via environment configuration
- Supabase Storage for private completion-evidence files
- row-level security patterns and backend authorization checks to keep private data protected

The configuration is centered in backend/app/core/config.py and environment settings are supplied via .env-based configuration.

## Supabase Storage

Private completion evidence is uploaded via authenticated FastAPI routes and stored in a dedicated storage bucket or equivalent private storage location configured through the backend. The flow is designed to keep user-uploaded completion evidence off the public frontend, while the backend remains the source of truth for validation.

## Supabase Realtime

Supabase Realtime is used as a delivery mechanism for authorization-safe realtime publication. It is not the authoritative source of data; the FastAPI backend remains authoritative for business logic and database mutations.

## Redis

Redis is used for:

- Celery broker connectivity
- Celery result backend storage
- lightweight session-like operational infrastructure for asynchronous tasks

## Celery

Celery tasks are used for asynchronous work and verification tasks. This project includes task infrastructure under backend/celery_app.py and a sample verification task in backend/app/tasks/sample_tasks.py.

## JWT + RBAC

Authentication is based on JWT access tokens. Role enforcement is enforced through backend dependencies and current-user checks for Consumer, Worker, and Admin endpoints. JWT expiry remains at 30 minutes.

## AI provider abstraction

The project includes an AI provider abstraction layer that supports multiple providers (for example Groq or Gemini) with fallback behavior and model configuration through settings. The abstraction is advisory and does not directly make hiring, payment, or dispute decisions.

## Simulated payment architecture

The payment architecture is intentionally simulated rather than connected to a live bank or UPI provider. It covers:

- agreement creation
- advance payment milestones
- final payment completion states
- payment records and status tracking
- clear separation between simulation and live financial provisioning

This is explicitly represented as simulated functionality, not a production payment integration.

## Job/application/negotiation/agreement flow

Typical flow:

1. Consumer posts a job
2. Workers view the job and apply with a proposed price
3. Consumer reviews applicants and accepts or rejects
4. Agreement is established for the chosen worker
5. Advance payment can be triggered
6. Work proceeds and completion evidence is uploaded
7. Both sides confirm completion or flag issues
8. Final payment is settled if business rules allow

## Scheduling/availability

Workers can maintain availability windows, review upcoming jobs, and resolve schedule conflicts in the backend. Consumers also see job timing context when reviewing jobs or work progress.

## Completion + dual evidence

Completion is a dual-confirmation flow involving both worker and consumer completion evidence. The system validates evidence type, image constraints, upload requirements, and confirmation states before final payment logic can complete.

## Reviews/ratings

After work is complete or concluded, reviews and ratings are stored so Workers and Consumers can maintain trust signals and accountability in the ecosystem.

## Complaints/disputes

The app includes complaint and dispute patterns for payment disputes, job issues, technical issues, and other operational concerns. These are job-linked and role-specific in the current implementation.

## Location intelligence

The project includes location intelligence for multiple use cases:

- Consumer nearby worker intelligence
- Worker Fair Opportunity and region analysis
- Admin geographic supply/demand intelligence
- map-based regional heatmap/marker rendering with Leaflet and OpenStreetMap

These services provide guidance and operational visibility, while backend authorization remains the source of truth.

## Consumer nearby worker intelligence

The Consumer flow can estimate nearby availability and local supply/demand based on area input. This supports better job posting and local matching without exposing sensitive private profile details.

## Worker Fair Opportunity

Workers can set a working location and radius, and the frontend uses the backend’s regional opportunity intelligence to show supply/demand context. This is advisory and is not a fabricated replacement for real backend data.

## Admin geographic supply/demand intelligence

The Admin flow includes region-based heatmap/marker summaries and search filters to inspect local supply and demand. It also persists the map state across refreshes/navigation to preserve operator context.

## Privacy/security/RLS

The backend expects privacy-first configuration and security-oriented design practices:

- JWT for authentication
- role checks for authorization
- backend validation before sensitive actions
- storage constraints for private media
- Supabase RLS patterns and hardened publication rules for public realtime content
- private media excluded from broad public publication

## Repository structure

- consumer-web/: consumer frontend UI and interactions
- worker-web/: worker frontend UI and interactions
- admin-web/: admin frontend UI and interactions
- backend/app/: API, services, auth, DB models, realtime, health, ai, providers
- backend/alembic/: migration scripts
- backend/tests/: regression and functionality tests
- shared/: shared UI layer and assets
- docs/: platform documentation and architecture references
- infra/: deployment and environment scaffolding

## Environment variables / .env.example

Create a local .env based on backend/.env.example and keep secrets local. Never commit credentials or tokens. Examples of expected variables include:

- DATABASE_URL or Supabase database settings
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_ANON_KEY
- JWT_SECRET_KEY
- REDIS_URL and Celery broker URLs
- AI provider API keys for Groq/Gemini if used
- SMTP configuration for email provider

The backend configuration reads from .env using the settings model in backend/app/core/config.py.

## Backend startup

From the backend directory:

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Consumer frontend startup

From the project root:

```bash
python -m http.server 5500 --directory consumer-web
```

Then open http://localhost:5500/ in the browser.

## Worker frontend startup

From the project root:

```bash
python -m http.server 5501 --directory worker-web
```

Then open http://localhost:5501/ in the browser.

## Admin frontend startup

From the project root:

```bash
python -m http.server 5502 --directory admin-web
```

Then open http://localhost:5502/ in the browser.

## Alembic migrations

Migrations are under backend/alembic/versions. Apply them with:

```bash
cd backend
alembic upgrade head
```

## Redis/Celery setup

A local Redis instance is expected for Celery and async infrastructure.

```bash
redis-server
celery -A celery_app.celery_app worker --loglevel=info
```

The app also supports a sample verification task for local sanity checks.

## Testing

Run the backend test suite from the backend directory:

```bash
pytest -q
```

Focused validation can include:

```bash
pytest backend/tests/test_auth.py backend/tests/test_completion.py -q
```

## Current simulated functionality

The current implementation includes simulated behavior for:

- simulated advance and final payment flows
- simulated notifications and operational states
- demo-ready local frontend flows without live external billing integrations
- platform-level intelligence that is advisory and backend-driven

## Genuine limitations / external dependencies

This project is a realistic demo platform, not a production-grade banking or labor marketplace. Important limitations include:

- no live payment processor integration
- no real-time worker identity verification or KYC
- no live file-processing or media AI moderation service
- external Supabase and Redis services must be configured for full runtime behavior
- local demo frontends are static and rely on backend APIs being available

## Future real-payment-provider replacement concept

The payment layer is intentionally isolated so it can eventually be replaced with a real provider (for example, a regulated payment gateway or bank transfer architecture) behind the same domain contracts. The current system models milestones and status transitions while preserving the same workflow shape.

## Implemented vs simulated

Implemented in the repository:

- role-based auth
- job posting and applications
- negotiation and agreements
- scheduling and availability windows
- simulated payments and completion states
- complaint flows
- notification and review patterns
- locality and fairness intelligence
- private completion evidence storage flow

Simulated or future-capable:

- real payment processing
- external provider integrations
- live financial settlement
- broader production monitoring

The project should be understood as a backend-driven local work demo platform with real API structure, database models, and operational workflows, while using simulated payments and demo-safe automation where live external services are not part of the repository scope.
