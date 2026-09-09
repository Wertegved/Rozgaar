(() => {
  let client;
  let channel;
  let reconnectTimer;
  let refreshTimer;
  let stopped = true;
  let options;
  let supabaseModule;
  const loadClient = () => new Promise((resolve, reject) => { if (supabaseModule) return resolve(supabaseModule); if (window.supabase) { supabaseModule = window.supabase; return resolve(supabaseModule); } const script = document.createElement('script'); script.src = 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2'; script.onload = () => { supabaseModule = window.supabase; resolve(supabaseModule); }; script.onerror = reject; document.head.appendChild(script); });
  const removeChannel = async () => { if (client && channel) await client.removeChannel(channel); channel = null; };
  const stop = async () => { clearTimeout(reconnectTimer); clearTimeout(refreshTimer); await removeChannel(); client = null; };
  const connect = async () => { if (stopped || !options?.token || !options?.user?.id) return; clearTimeout(reconnectTimer); clearTimeout(refreshTimer); await removeChannel(); try { const response = await fetch(`${options.apiBase}/realtime/token`, { headers: { Authorization: `Bearer ${options.token}` } }); const config = await response.json(); if (!response.ok) throw new Error(config.detail || 'Realtime authorization failed.'); const supabase = await loadClient(); if (!client) client = supabase.createClient(config.supabase_url, config.supabase_anon_key, { auth: { persistSession: false, autoRefreshToken: false }, accessToken: async () => config.access_token }); channel = client.channel(config.channel, { config: { private: true } }).on('broadcast', { event: 'rozgaar.event' }, event => options.onEvent?.(event.payload)).subscribe(status => { options.onStatus?.(status); if (status === 'SUBSCRIBED') refreshTimer = setTimeout(connect, 12 * 60 * 1000); if (['CHANNEL_ERROR', 'TIMED_OUT', 'CLOSED'].includes(status)) reconnectTimer = setTimeout(connect, 3000); }); } catch (error) { options.onStatus?.('ERROR'); reconnectTimer = setTimeout(connect, 3000); } };
  window.RozgaarRealtime = { start(next) { stopped = false; options = next; return connect(); }, stop() { stopped = true; options = null; return stop(); } };
})();
