-- Rozgaar private Broadcast channel authorization.
-- Apply in the Supabase SQL Editor if the managed realtime schema is not writable
-- through the application database connection.

alter table if exists realtime.messages enable row level security;

drop policy if exists rozgaar_realtime_private_channel_select on realtime.messages;
create policy rozgaar_realtime_private_channel_select
on realtime.messages
for select
to authenticated
using (
  topic = 'user:' || auth.uid()::text
);
