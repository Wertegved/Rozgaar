# Rozgaar Backend

FastAPI foundation for the Rozgaar platform.

## Local development

From the `backend` directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The health endpoints are available at `/health`, `/ready`, `/api/v1/health`, and `/api/v1/ready`. OpenAPI documentation is available at `/docs`.

Set local values in an untracked `.env` file. Do not place credentials in source files or frontend applications.

## Background tasks (Phase 14)

Redis is used locally as the Celery broker and result backend. It is infrastructure only; PostgreSQL/Supabase remains the source of truth. Configure `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` in `.env` for the target environment.

Run the three local processes from the `backend` directory:

```powershell
# Terminal 1: FastAPI
uvicorn app.main:app --reload

# Terminal 2: Redis (requires a local Redis installation)
redis-server

# Terminal 3: Celery worker
celery -A celery_app.celery_app worker --loglevel=info
```

The harmless verification task can be enqueued from a Python shell with `from app.tasks.sample_tasks import verify_task; result = verify_task.delay("phase-14")`; inspect `result.id`, `result.state`, and `result.get()` after the worker processes it. Celery tasks must tolerate duplicate delivery and should receive primitive identifiers/data rather than database sessions or ORM objects. Live Redis/worker checks are optional; the normal test suite does not require Redis to be running.

## AI provider infrastructure (Phase 15)

Phase 15 adds a provider-agnostic `AIService` for future application features. Groq is the primary provider using `meta-llama/llama-4-scout-17b-16e-instruct`; Google Gemini is the fallback using `gemini-3.8-flash`. Provider SDKs are isolated under `app/ai/providers`, and future business services should depend on `AIService` and its interfaces rather than either SDK.

Configure local credentials only in the untracked `.env` file:

```text
AI_PRIMARY_PROVIDER=groq
AI_PRIMARY_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
GROQ_API_KEY=
AI_FALLBACK_PROVIDER=gemini
AI_FALLBACK_MODEL=gemini-3.8-flash
GEMINI_API_KEY=
AI_REQUEST_TIMEOUT_SECONDS=30
AI_MAX_RETRIES=2
```

Keys may remain empty for application startup and tests. `FakeAIProvider` is available for network-free unit tests. The service retries transient rate-limit, timeout, and temporary-unavailable failures a bounded number of times, then tries Gemini once through its own bounded attempt; invalid requests and configuration errors are not silently hidden by fallback. Structured responses are parsed and validated with Pydantic, and image inputs use provider-neutral in-memory bytes and MIME types.

AI is advisory infrastructure only. It does not directly change authoritative database state, hire or reject workers, modify agreements or payments, complete jobs, ban users, or resolve disputes. Never put API keys in source, tests, README files, frontend code, logs, or database records, and send providers only the minimum necessary information.

## Realtime infrastructure (Phase 14)

Supabase Realtime delivers authorized PostgreSQL changes to later consumer, worker, and admin frontends. The backend remains responsible for authentication, authorization, validation, business rules, and all database mutations. Realtime is a delivery mechanism, not the source of truth.

The migration `c3d4e5f6a7b8_realtime_publication` adds only these existing tables to the `supabase_realtime` publication when that publication exists: jobs, applications, agreements, worker availability, payments, completions, completion worker states, reviews, complaints, disputes, and notifications. Private media tables and user credential fields are excluded. Apply it with the normal `alembic upgrade head` workflow; no duplicate event table or websocket server is introduced.

Realtime event contracts cover job, application, agreement, availability, payment, completion, review, complaint, dispute, and notification changes. Recipient scopes are derived from server-loaded ownership and participant relationships, with admin-only scopes for operational events. Payload helpers remove credentials, contact details, and private Storage references. The persistent database and existing FastAPI APIs remain authoritative: clients reconnect by fetching current authorized state, and duplicate delivery is harmless. A realtime delivery failure is logged and does not roll back a successful business transaction.

Local tests use the event contract and a fake delivery transport; they do not require a Supabase websocket or live database. Frontend subscription code belongs to later frontend phases and must use only safe public Supabase configuration, never the service-role key.

## Authentication

Phase 5 provides:

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

Registration accepts `CONSUMER` and `WORKER` roles. Public `ADMIN` registration is rejected; administrators require a later controlled provisioning process. Passwords are hashed with Argon2id, and login returns a short-lived JWT bearer token.

Set a strong local `JWT_SECRET_KEY` in the untracked backend `.env` before using login. Never commit it, place it in frontend code, or print it in logs. `JWT_ALGORITHM` defaults to `HS256`, and `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` defaults to `30`.

Database connectivity and all non-authentication business functionality remain phase-specific work.

## Job management

Phase 6 provides authenticated backend endpoints for:

- `POST /api/v1/jobs` for consumer-owned job creation
- `GET /api/v1/jobs` for worker discovery, consumer-owned listings, and admin reads
- `GET /api/v1/jobs/{job_id}` for job details
- `PATCH /api/v1/jobs/{job_id}` for owner-only mutable details

Listings support category, emergency level, scheduled date, location, price range, worker count, status, and bounded page pagination. Job image entries store private Supabase Storage references only; no upload or Storage policy workflow is implemented. Workers can discover and inspect jobs but cannot apply or change them.

## Applications and hiring

Phase 7 provides:

- `POST /api/v1/jobs/{job_id}/applications` for worker applications with Decimal proposals
- `GET /api/v1/applications/my` for the authenticated worker's applications
- `GET /api/v1/jobs/{job_id}/applications` for the owning consumer's applicants
- `POST /api/v1/applications/{application_id}/accept`
- `POST /api/v1/applications/{application_id}/reject`
- `POST /api/v1/applications/{application_id}/withdraw`
- `POST /api/v1/applications/{application_id}/counter-offer`
- `POST /api/v1/negotiations/{negotiation_id}/accept`
- `POST /api/v1/negotiations/{negotiation_id}/counter-offer`
- `POST /api/v1/negotiations/{negotiation_id}/reject`

Applications use explicit backend-controlled transitions. Negotiation records preserve each proposal. Hiring creates an `ACTIVE` agreement using the job's existing scheduled date and times; those fields must exist before hiring. Agreement fields have no update endpoint and are treated as locked. No payment, scheduling engine, notifications, or realtime behavior is included.

## Scheduling and availability

Phase 8 adds explicit date-based worker availability and derives schedules from active agreements:

- `POST/GET/PATCH/DELETE /api/v1/workers/me/availability...`
- `GET /api/v1/workers/me/schedule`
- `GET /api/v1/workers/me/upcoming-jobs`
- `GET /api/v1/jobs/{job_id}/schedule`

Availability windows must remain within one day and may not overlap. Agreement scheduling rejects uncovered configured availability and overlapping active agreements; touching boundaries such as `10:00-12:00` and `12:00-14:00` are allowed. No rescheduling, calendar engine, payment, completion, notification, or realtime behavior is included.

## Payments

Phase 9 uses only the `simulated` provider. `POST /api/v1/agreements/{agreement_id}/payments/advance` derives a 20% advance from the locked agreement amount, records a completed simulated advance, and prepares a pending final-payment record. Repeated advance requests reuse the completed record. Final payment is not released in this phase and no real payment gateway or financial credential is used.

## Completion milestones

Phase 10 provides milestone-based completion endpoints:

- `POST /api/v1/jobs/{job_id}/completion/worker`
- `POST /api/v1/jobs/{job_id}/completion/consumer`
- `GET /api/v1/jobs/{job_id}/completion`

Each participant submits one private `completion-evidence` Storage reference together with their independent confirmation. No upload API, public URL, periodic evidence, surveillance, or continuous collection is implemented. After all active worker agreements and both participant milestones are satisfied, the Completion Service invokes the existing simulated Payment Service for the backend-derived final balance; only a successful final payment changes the job to `COMPLETED`.

## Reviews and reputation

Phase 11 provides:

- `POST /api/v1/jobs/{job_id}/reviews`
- `GET /api/v1/jobs/{job_id}/reviews`
- `GET /api/v1/users/{user_id}/reviews`
- `GET /api/v1/reviews/my`

Reviews are immutable, available only for completed jobs, and restricted to the consumer and legitimately hired workers connected to that job. Reputation is derived from stored reviews; no editable rating cache, ranking, moderation, or recommendation system is included.

## Complaints and disputes

Phase 12 provides structured issue reporting and neutral admin investigation:

- `POST /api/v1/complaints`
- `GET /api/v1/complaints/my`
- `GET /api/v1/complaints/{complaint_id}`
- `GET/PATCH/POST /api/v1/admin/complaints...`
- `POST /api/v1/jobs/{job_id}/disputes`
- `GET /api/v1/disputes/{dispute_id}` for associated participants
- `GET/PATCH/POST /api/v1/admin/disputes...`

Complaint and dispute identities are derived from authentication. Job-linked reports require legitimate participation. Admin resolution records factual resolution text and status only; issue creation does not refund payments, change completion, alter reviews, classify users, or trigger external escalation.

## Notifications and email (Phase 15)

Phase 15 provides an authenticated, persistent notification inbox:

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{notification_id}/read`
- `POST /api/v1/notifications/read-all`

Notification records in PostgreSQL are the source of truth. Supabase Realtime and email are delivery mechanisms only. Notification creation is idempotent per recipient and backend-generated event key, and notification services never commit or roll back the caller's transaction. Listing is ordered by `created_at DESC, id DESC`, scoped to the JWT user, and supports unread filtering and counts.

Email delivery uses the provider-neutral `EmailProvider` interface. `FakeEmailProvider` is the default in `.env.example` for tests and local development; `SMTPEmailProvider` uses `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_FROM_NAME`. All mail uses the configured Rozgaar sender identity. Missing SMTP configuration or provider/network errors are logged safely and do not roll back business state or remove the persisted notification. No real email calls are made by tests.

Supported notification events include application and counter-offer changes, agreements, payments, completion, reviews, complaints, disputes, job status, schedules, and account events. Recipients are resolved from authenticated business relationships; clients cannot choose a recipient user or email. Private credentials, contact data, and Storage references are not placed in notification content.

## Database foundation

Set `DATABASE_URL` to the Supabase PostgreSQL connection string in the untracked backend `.env` file, then run migrations from this directory:

```powershell
alembic upgrade head
```

The initial migration is `45badac89889_initial_schema`. It is a source-controlled Alembic revision generated from the SQLAlchemy declarative metadata. Apply the current Alembic head to include the Phase 14 Realtime publication and Phase 16 security policies; no seed data is included.

## Security and RLS hardening (Phase 16)

FastAPI remains the application authorization and business-logic layer. JWT identity is decoded with the configured algorithm and secret, then resolved against an active database user; request-body roles and ownership fields are never trusted. Admin routes require the authenticated database role, and resource access is checked by ownership or participant relationship rather than UUID possession.

Migration `e5f6a7b8c9d0_security_rls_hardening` enables defense-in-depth PostgreSQL RLS for the domain tables. Supabase client policies derive identity from `request.jwt.claim.sub` and the authoritative `users` row, with explicit policies for users, jobs, applications, agreements, payments, completion data, complaints, disputes, and notifications. The existing backend uses a server-side database connection, so RLS is enabled but not forced onto the backend owner connection; direct Supabase access remains deny-by-default unless a policy grants it. Run `python -m alembic upgrade head` against the target PostgreSQL database to apply it.

The private Storage buckets `job-images`, `completion-evidence`, and `approved-media` remain private. The migration denies direct Storage reads, inserts, updates, and deletes until a resource-aware signed-access workflow is introduced; the backend validates bucket names and rejects absolute, URL, and traversal paths. No public URLs or service-role credentials are returned. This is intentional fail-closed behavior, not a frontend restriction.

Security tests cover authentication boundaries, admin/RBAC enforcement, mass-assignment rejection, job ownership, notification isolation, private payload filtering, path traversal, secret handling, and the RLS migration contract. PostgreSQL RLS policy execution requires the configured Supabase/PostgreSQL environment and is not required for the local SQLite test suite.