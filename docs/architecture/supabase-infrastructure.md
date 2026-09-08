# Supabase Infrastructure Preparation

Status: preparation only. No Supabase project, database schema, application tables, policies, subscriptions, or application code are configured by this repository.

## Configuration boundaries

The root `.env.example` contains names for non-privileged frontend configuration only:

- `PUBLIC_SUPABASE_URL`
- `PUBLIC_SUPABASE_ANON_KEY`

The backend `.env.example` contains names for backend-only configuration:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_DB_URL`
- `SUPABASE_DB_DIRECT_URL`

Populate real values only in untracked local environment files or the deployment secret manager. Never expose `SUPABASE_SERVICE_ROLE_KEY`, database URLs, or database passwords to any frontend. The service-role key is privileged and must remain backend-only.

`SUPABASE_DB_URL` is intended for the future application connection pool. `SUPABASE_DB_DIRECT_URL` is intended for future administrative or migration connections. No connection is opened by this phase.

## Required Supabase Dashboard actions

These actions require a human with access to the Rozgaar Supabase project:

1. Create or select the Rozgaar Supabase project and record its project URL and project reference.
2. In **Connect**, copy the PostgreSQL connection details appropriate for the deployment into a secret manager. Prefer the Supavisor pooled connection for application traffic and retain a direct connection only for controlled migration operations.
3. In **Storage**, create these private buckets:
   - `job-images`
   - `completion-evidence`
   - `approved-job-media`
4. Keep all three buckets private. Future signed URLs or backend-mediated access must be limited to authorized parties and short-lived where practical.
5. In **Database > Publications**, enable Realtime only for future tables after their schema and access rules are reviewed. Realtime must remain a delivery mechanism; FastAPI remains the source of truth.
6. Do not disable RLS. Enable it on every future application table before application access is introduced.

## Storage access intent

Future backend policies and APIs must enforce ownership and job authorization. Consumers may access only media for jobs they are authorized to view. Workers may access only media required for their assigned or accepted work. Admin access must be explicitly authenticated and audited. Private objects must not be made publicly readable as a development shortcut.

## RLS preparation

No RLS policies are created in this phase because the application tables do not exist. Future RLS review is required for at least:

- users and role/profile data
- jobs
- job applications
- agreements and negotiations
- payments
- completion evidence and media metadata
- disputes and complaints
- reviews
- administrative operational records

Future policies must enforce authenticated ownership and role membership for `CONSUMER`, `WORKER`, and `ADMIN`. Before worker acceptance, consumers must not receive private worker contact or sensitive information; before acceptance, workers must not receive unnecessary private consumer information. After acceptance, only the information needed to perform the job may be visible to authorized parties. A worker's exact location must never be unnecessarily exposed to consumers. Administrative access must require the appropriate protected role.

## Verification status

Project credentials and a Supabase project reference were not supplied in this workspace. Therefore project availability, PostgreSQL connectivity, Storage buckets, Realtime publication settings, and dashboard security settings remain unverified and require the Dashboard actions above. No credentials were guessed, generated, or committed.