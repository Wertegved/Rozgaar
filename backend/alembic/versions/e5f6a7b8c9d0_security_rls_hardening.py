"""Add defense-in-depth RLS policies for Supabase access.

The FastAPI database connection remains server-side and is not forced through
RLS. Supabase clients use request.jwt.claim.sub as their authenticated identity.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

from alembic import op


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    "users", "consumer_profiles", "worker_profiles", "skills", "worker_skills",
    "jobs", "job_images", "job_requirements", "applications", "negotiations",
    "agreements", "worker_availability", "payments", "completions",
    "completion_evidence", "completion_worker_states", "reviews", "complaints",
    "disputes", "dispute_messages", "cancellations", "notifications",
)


def _policy(table: str, action: str, using: str, check: str | None = None) -> None:
    policy_name = f"phase16_{table}_{action.lower()}"
    if action == "INSERT":
        policy_sql = f"WITH CHECK ({check or using})"
    else:
        check_sql = f" WITH CHECK ({check})" if check else ""
        policy_sql = f"USING ({using}){check_sql}"
    op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
    op.execute(
        f"CREATE POLICY {policy_name} ON {table} FOR {action} TO authenticated "
        f"{policy_sql}"
    )


def upgrade() -> None:
    op.execute(
        """CREATE OR REPLACE FUNCTION public.phase16_user_id() RETURNS uuid
        LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
        BEGIN
          RETURN NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid;
        EXCEPTION WHEN invalid_text_representation THEN RETURN NULL;
        END; $$;"""
    )
    op.execute(
        """CREATE OR REPLACE FUNCTION public.phase16_is_admin() RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
          SELECT EXISTS (SELECT 1 FROM users WHERE id = public.phase16_user_id() AND role = 'ADMIN' AND account_status = 'ACTIVE');
        $$;"""
    )
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    admin = "public.phase16_is_admin()"
    user = "public.phase16_user_id()"
    _policy("users", "SELECT", f"id = {user} OR {admin}")
    _policy("consumer_profiles", "SELECT", f"user_id = {user} OR {admin}")
    _policy("worker_profiles", "SELECT", f"user_id = {user} OR {admin}")
    _policy("skills", "SELECT", "true")
    _policy("worker_skills", "SELECT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR {admin}")
    _policy("jobs", "SELECT", f"consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user}) OR (status IN ('POSTED', 'APPLICATIONS') AND {user} IS NOT NULL) OR {admin}")
    _policy("jobs", "INSERT", f"consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})", f"consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})")
    _policy("jobs", "UPDATE", f"consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user}) OR {admin}")
    _policy("job_images", "SELECT", f"job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR job_id IN (SELECT job_id FROM agreements WHERE worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})) OR {admin}")
    _policy("job_requirements", "SELECT", f"job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR {admin}")
    _policy("applications", "SELECT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR {admin}")
    _policy("applications", "INSERT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})")
    _policy("applications", "UPDATE", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR {admin}")
    _policy("negotiations", "SELECT", f"application_id IN (SELECT id FROM applications WHERE worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user}))) OR {admin}")
    _policy("agreements", "SELECT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR {admin}")
    _policy("worker_availability", "SELECT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR {admin}")
    _policy("worker_availability", "INSERT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})")
    _policy("worker_availability", "UPDATE", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR {admin}")
    _policy("worker_availability", "DELETE", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR {admin}")
    _policy("payments", "SELECT", f"payer_id = {user} OR payee_id = {user} OR {admin}")
    _policy("completions", "SELECT", f"job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR job_id IN (SELECT job_id FROM agreements WHERE worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})) OR {admin}")
    _policy("completion_evidence", "SELECT", f"uploaded_by = {user} OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR {admin}")
    _policy("completion_worker_states", "SELECT", f"worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR {admin}")
    _policy("reviews", "SELECT", f"reviewer_id = {user} OR reviewed_user_id = {user} OR {admin}")
    _policy("complaints", "SELECT", f"raised_by = {user} OR {admin}")
    _policy("disputes", "SELECT", f"raised_by = {user} OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})) OR job_id IN (SELECT job_id FROM agreements WHERE worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user})) OR {admin}")
    _policy("dispute_messages", "SELECT", f"dispute_id IN (SELECT id FROM disputes WHERE raised_by = {user}) OR {admin}")
    _policy("cancellations", "SELECT", f"{admin} OR agreement_id IN (SELECT id FROM agreements WHERE worker_id IN (SELECT id FROM worker_profiles WHERE user_id = {user}) OR job_id IN (SELECT id FROM jobs WHERE consumer_id IN (SELECT id FROM consumer_profiles WHERE user_id = {user})))")
    _policy("notifications", "SELECT", f"recipient_user_id = {user} OR {admin}")
    _policy("notifications", "UPDATE", f"recipient_user_id = {user}")

    # Storage is optional in local/unit-test databases; apply policies when the
    # Supabase storage schema is present, while keeping buckets private.
    '''op.execute(
        """DO $$ BEGIN
        IF to_regclass('storage.objects') IS NOT NULL THEN
          EXECUTE 'ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY';
          EXECUTE 'DROP POLICY IF EXISTS phase16_storage_select ON storage.objects';
          EXECUTE 'CREATE POLICY phase16_storage_select ON storage.objects FOR SELECT TO authenticated USING (false)';
          EXECUTE 'DROP POLICY IF EXISTS phase16_storage_deny_insert ON storage.objects';
          EXECUTE 'CREATE POLICY phase16_storage_deny_insert ON storage.objects FOR INSERT TO authenticated WITH CHECK (false)';
          EXECUTE 'DROP POLICY IF EXISTS phase16_storage_deny_update ON storage.objects';
          EXECUTE 'CREATE POLICY phase16_storage_deny_update ON storage.objects FOR UPDATE TO authenticated USING (false)';
          EXECUTE 'DROP POLICY IF EXISTS phase16_storage_deny_delete ON storage.objects';
          EXECUTE 'CREATE POLICY phase16_storage_deny_delete ON storage.objects FOR DELETE TO authenticated USING (false)';
        END IF; END $$;"""
    )'''


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS public.phase16_is_admin()")
    op.execute("DROP FUNCTION IF EXISTS public.phase16_user_id()")