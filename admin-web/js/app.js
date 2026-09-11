const API_BASE = localStorage.getItem('rozgaar_api_base') || 'https://rozgaar-backend-v34k.onrender.com/api/v1';

const state = {
  token: localStorage.getItem('rozgaar_token'),
  user: null,
  jobs: [],
  notifications: [],
  unreadCount: 0,
  complaints: [],
  users: [],
  usersPage: 1,
  usersPageSize: 20,
  usersTotal: 0,
  disputes: [],
  payments: [],
  paymentSummary: 0,
  view: 'dashboard',
  drawerOpen: false,
  eventsBound: false,
  adminMap: null,
  adminMapBounds: null,
  adminMapLayers: [],
};
const ADMIN_HEATMAP_SESSION_KEY = 'rozgaar_admin_heatmap_state';
if (sessionStorage.getItem(ADMIN_HEATMAP_SESSION_KEY)) state.view = 'heatmap';

const navItems = [
  { id: 'home', label: 'Home' },
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'heatmap', label: 'Area / Heatmap' },
  { id: 'jobs', label: 'Jobs' },
  { id: 'workforce', label: 'Workforce' },
  { id: 'disputes', label: 'Disputes' },
  { id: 'payments', label: 'Payments' },
  { id: 'complaints', label: 'Complaints' },
  { id: 'analytics', label: 'Analytics' },
  { id: 'users', label: 'User management' },
];

const $ = (selector, scope = document) => scope.querySelector(selector);
const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];

const money = (value) => {
  if (value === undefined || value === null || value === '') return '—';
  return `₹${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
};

const dateLabel = (value) => {
  if (!value) return 'Flexible date';
  return new Intl.DateTimeFormat('en-IN', { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value));
};

const timeLabel = (value) => {
  if (!value) return '—';
  if (typeof value === 'string') return value.slice(0, 5);
  return value;
};

const escapeHtml = (value) => {
  if (value === null || value === undefined) return '';
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
};

const statusLabel = (value) => String(value || 'UNKNOWN').replace(/_/g, ' ');

async function api(path, options = {}) {
  const headers = { Accept: 'application/json', ...(options.headers || {}) };
  if (state.token && !headers.Authorization) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  if (options.body && !(options.headers && options.headers['Content-Type'])) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 204) return null;

  const text = await response.text();
  let body = {};
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = {};
  }

  if (!response.ok) {
    const detail = body?.detail || body?.error?.detail || 'The request failed.';
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg || item).join(', ') : detail);
  }

  return body;
}

function toast(message) {
  const node = document.getElementById('toast');
  if (!node) return;
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), 3200);
}

function openDrawer(content) {
  const backdrop = document.getElementById('drawer-backdrop');
  const drawer = document.getElementById('drawer');
  if (!backdrop || !drawer) return;
  drawer.innerHTML = content;
  backdrop.classList.add('is-open');
  drawer.classList.add('is-open');
  state.drawerOpen = true;
}

function closeDrawer() {
  const backdrop = document.getElementById('drawer-backdrop');
  const drawer = document.getElementById('drawer');
  if (!backdrop || !drawer) return;
  drawer.classList.remove('is-open');
  backdrop.classList.remove('is-open');
  drawer.innerHTML = '';
  state.drawerOpen = false;
}

function renderShell() {
  document.body.innerHTML = `
    <div class="admin-shell">
      <aside class="sidebar">
        <div class="brand-lockup">
          <div class="brand-mark">r</div>
          <div class="brand-text">Rozgaar</div>
        </div>
        <nav class="nav-stack" aria-label="Admin navigation">
          ${navItems.map((item) => `
            <button
              type="button"
              class="nav-item ${state.view === item.id ? 'is-active' : ''}"
              data-view="${item.id}"
              aria-current="${state.view === item.id ? 'page' : 'false'}"
            >
              <span>${escapeHtml(item.label)}</span>
              <small>${item.id === 'home' ? '—' : item.id === 'dashboard' ? '01' : item.id === 'heatmap' ? '02' : item.id === 'jobs' ? '03' : item.id === 'workforce' ? '04' : item.id === 'disputes' ? '05' : item.id === 'payments' ? '06' : item.id === 'complaints' ? '07' : item.id === 'analytics' ? '08' : '09'}</small>
            </button>
          `).join('')}
        </nav>
        <div class="sidebar-footer">
          Cooperative operations view<br>
          <strong>${state.user ? escapeHtml(state.user.name) : 'Signed out'}</strong>
        </div>
      </aside>

      <div class="content">
        <header class="topbar">
          <div class="topbar-left">
            <div>
              <div class="page-kicker">Cooperative admin</div>
              <h1 class="topbar-title">${state.user ? 'Operations view' : 'Access required'}</h1>
            </div>
          </div>
          <div class="topbar-actions">
            ${state.user ? `
              <div class="user-pill">
                <span class="avatar-mini">${escapeHtml((state.user.name || 'A').charAt(0).toUpperCase())}</span>
                <span>${escapeHtml(state.user.name || 'Admin')}</span>
              </div>
              <button type="button" class="secondary-button notification-button" data-action="open-notifications" aria-label="Open notifications">
                Notifications${state.unreadCount ? `<span class="notification-count">${state.unreadCount > 99 ? '99+' : state.unreadCount}</span>` : ''}
              </button>
              <button type="button" class="secondary-button" data-action="refresh-data">Refresh</button>
              <button type="button" class="primary-button" data-action="logout">Logout</button>
            ` : `
              <button type="button" class="primary-button" data-action="login-cta">Log in</button>
            `}
          </div>
        </header>
        <main class="main-panel" id="main-panel"></main>
      </div>
    </div>

    <div class="drawer-backdrop" id="drawer-backdrop" aria-hidden="true"></div>
    <aside class="drawer" id="drawer" aria-hidden="true"></aside>
    <div class="toast" id="toast" aria-live="polite"></div>
  `;

  bindGlobalEvents();
  renderMainContent();
}

function bindGlobalEvents() {
  if (state.eventsBound) return;
  state.eventsBound = true;

  document.addEventListener('click', async (event) => {
    const viewButton = event.target.closest('[data-view]');
    if (viewButton) {
      const view = viewButton.dataset.view;
      if (view && view !== state.view) {
        state.view = view;
        renderShell();
      }
      return;
    }

    const action = event.target.closest('[data-action]');
    if (!action) return;

    switch (action.dataset.action) {
      case 'logout':
        signOut();
        break;
      case 'login-cta':
        renderLogin();
        break;
      case 'refresh-data':
        await refreshData();
        break;
      case 'refresh-users':
        await loadUsersView();
        break;
      case 'users-prev':
        if (state.usersPage > 1) { state.usersPage -= 1; await loadUsersView(); }
        break;
      case 'users-next':
        if (state.usersPage * state.usersPageSize < state.usersTotal) { state.usersPage += 1; await loadUsersView(); }
        break;
      case 'open-admin-user':
        await openAdminUser(action.dataset.id);
        break;
      case 'open-notifications':
        await openNotificationsDrawer();
        break;
      case 'close-drawer':
        closeDrawer();
        break;
      case 'mark-notification-read':
        await markNotificationRead(action.dataset.id);
        break;
      case 'mark-all-read':
        await markAllRead();
        break;
      case 'view-job':
        openJobDrawer(action.dataset.id);
        break;
      case 'view-dispute':
        openDisputeDrawer(action.dataset.id);
        break;
      case 'view-complaint':
        openComplaintDrawer(action.dataset.id);
        break;
      case 'resolve-dispute':
        await resolveDispute(action.dataset.id);
        break;
      case 'set-dispute-status':
        await updateDisputeStatus(action.dataset.id, action.dataset.status);
        break;
      case 'set-complaint-status':
        await updateComplaintStatus(action.dataset.id, action.dataset.status);
        break;
      case 'respond-complaint':
        await respondToComplaint(action.dataset.id);
        break;
      case 'reset-admin-map':
        resetAdminMapView();
        break;
      default:
        break;
    }
  });

  document.addEventListener('submit', async (event) => {
    const form = event.target;
    if (form.id === 'admin-login-form') {
      event.preventDefault();
      await handleLogin(form);
    }
    if (form.id === 'dispute-resolution-form') {
      event.preventDefault();
      const resolution = form.querySelector('[name="resolution"]').value.trim();
      const disputeId = form.dataset.disputeId;
      if (!resolution) {
        form.querySelector('.form-error').textContent = 'Please provide a resolution summary.';
        return;
      }
      try {
        await api(`/admin/disputes/${disputeId}/resolve`, {
          method: 'POST',
          body: JSON.stringify({ resolution }),
        });
        form.querySelector('.form-error').textContent = '';
        toast('Dispute resolution recorded.');
        await refreshData();
        closeDrawer();
      } catch (error) {
        form.querySelector('.form-error').textContent = error.message;
      }
    }
    if (form.id === 'complaint-response-form') {
      event.preventDefault();
      const responseText = form.querySelector('[name="response"]').value.trim();
      const complaintId = form.dataset.complaintId;
      if (!responseText) {
        form.querySelector('.form-error').textContent = 'Please provide a response.';
        return;
      }
      try {
        await api(`/admin/complaints/${complaintId}/response`, {
          method: 'POST',
          body: JSON.stringify({ response: responseText }),
        });
        form.querySelector('.form-error').textContent = '';
        toast('Complaint response saved.');
        await refreshData();
        closeDrawer();
      } catch (error) {
        form.querySelector('.form-error').textContent = error.message;
      }
    }
  });

  document.getElementById('drawer-backdrop')?.addEventListener('click', closeDrawer);
}

async function refreshData() {
  if (!state.token) {
    renderLogin();
    return;
  }

  try {
    const [me, jobs, notifications, unread, payments, disputes, complaints] = await Promise.all([
      api('/auth/me'),
      api('/jobs?page=1&page_size=100'),
      api('/notifications?page=1&page_size=50'),
      api('/notifications/unread-count'),
      api('/admin/payments').catch(() => ({ items: [], simulated_transaction_value: 0 })),
      api('/admin/disputes').catch(() => []),
      api('/admin/complaints').catch(() => ({ items: [] })),
    ]);

    state.user = me;
    state.jobs = jobs?.items || [];
    state.notifications = notifications?.items || [];
    state.unreadCount = Number(unread?.count || 0);
    state.payments = payments?.items || [];
    state.paymentSummary = Number(payments?.simulated_transaction_value ?? 0);
    state.disputes = disputes || [];
    state.complaints = complaints?.items || [];

    if (state.user.role !== 'ADMIN') {
      toast('This account does not have admin permissions.');
      state.token = null;
      localStorage.removeItem('rozgaar_token');
      renderLogin();
      return;
    }

    renderShell();
    window.RozgaarRealtime?.start({ apiBase: API_BASE, token: state.token, user: state.user, onEvent: () => refreshData(), onStatus: status => document.body.dataset.realtimeStatus = status });
    toast('Operations data refreshed.');
  } catch (error) {
    state.user = null;
    renderLogin();
    toast(error.message || 'Could not load admin data.');
  }
}

function renderMainContent() {
  const panel = document.getElementById('main-panel');
  if (!panel) return;

  if (!state.token || !state.user) {
    renderLogin();
    return;
  }

  if (state.view === 'home') {
    panel.innerHTML = renderHomeView();
    return;
  }

  if (state.view === 'dashboard') {
    panel.innerHTML = renderDashboardView();
    return;
  }

  if (state.view === 'heatmap') {
    const html = renderHeatmapView();
    panel.innerHTML = html;
    bindHeatmapControls();
    if (!restoreAdminHeatmapState()) loadAdminHeatmapData();
    return;
  }

  if (state.view === 'jobs') {
    panel.innerHTML = renderJobsView();
    bindJobsFilters();
    return;
  }

  if (state.view === 'workforce') {
    panel.innerHTML = renderWorkforceView();
    return;
  }

  if (state.view === 'disputes') {
    panel.innerHTML = renderDisputesView();
    return;
  }

  if (state.view === 'payments') {
    panel.innerHTML = renderPaymentsView();
    return;
  }

  if (state.view === 'complaints') {
    panel.innerHTML = renderComplaintsView();
    return;
  }

  if (state.view === 'analytics') {
    panel.innerHTML = renderAnalyticsView();
    return;
  }

  if (state.view === 'users') {
    panel.innerHTML = renderUsersView();
    loadUsersView();
    return;
  }

  panel.innerHTML = renderDashboardView();
}

function renderLogin() {
  bindGlobalEvents();
  document.body.innerHTML = `
    <div class="login-shell">
      <div class="login-card">
        <div class="eyebrow">Rozgaar admin</div>
        <h1>One cooperative view.</h1>
        <p>Use the existing admin account flow to access cooperative operations, payments, disputes, and support work.</p>
        <form id="admin-login-form" class="form-grid">
          <div class="field">
            <label for="admin-email">Email</label>
            <input id="admin-email" name="email" type="email" autocomplete="email" required>
          </div>
          <div class="field">
            <label for="admin-password">Password</label>
            <input id="admin-password" name="password" type="password" autocomplete="current-password" required>
          </div>
          <button type="submit" class="primary-button">Enter admin workspace</button>
          <div class="form-error" id="login-error"></div>
        </form>
        <div class="form-footnote">No separate admin registration flow is created here. Access is controlled by the existing FastAPI auth and RBAC checks.</div>
      </div>
    </div>
  `;
}

async function handleLogin(form) {
  const email = form.querySelector('[name="email"]').value.trim();
  const password = form.querySelector('[name="password"]').value.trim();
  const errorBox = document.getElementById('login-error');
  errorBox.textContent = '';

  if (!email || !password) {
    errorBox.textContent = 'Email and password are required.';
    return;
  }

  try {
    const result = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });

    if (!result?.access_token) {
      throw new Error('No access token returned.');
    }

    state.token = result.access_token;
    localStorage.setItem('rozgaar_token', state.token);
    state.user = result.user;

    if (state.user.role !== 'ADMIN') {
      state.token = null;
      localStorage.removeItem('rozgaar_token');
      errorBox.textContent = 'This account is not an admin. Please sign in with an administrative account.';
      return;
    }

    await refreshData();
  } catch (error) {
    errorBox.textContent = error.message;
  }
}

function signOut() {
  window.RozgaarRealtime?.stop();
  state.token = null;
  state.user = null;
  localStorage.removeItem('rozgaar_token');
  state.view = 'dashboard';
  renderLogin();
  toast('You have been signed out.');
}

async function markNotificationRead(id) {
  try {
    await api(`/notifications/${id}/read`, { method: 'POST' });
    await refreshNotifications();
    renderNotificationDrawer();
    toast('Notification marked as read.');
  } catch (error) {
    toast(error.message);
  }
}

async function markAllRead() {
  try {
    await api('/notifications/read-all', { method: 'POST' });
    await refreshNotifications();
    renderNotificationDrawer();
    toast('All notifications marked as read.');
  } catch (error) {
    toast(error.message);
  }
}

async function refreshNotifications() {
  const [notifications, unread] = await Promise.all([
    api('/notifications?page=1&page_size=50'),
    api('/notifications/unread-count'),
  ]);
  state.notifications = notifications?.items || [];
  state.unreadCount = Number(unread?.count || 0);
}

function renderNotificationDrawer() {
  const items = state.notifications;
  const content = `
    <div class="drawer-head">
      <div class="drawer-heading">
        <div class="eyebrow">Admin inbox</div>
        <h2>Notifications</h2>
      </div>
      <button type="button" class="close-button" data-action="close-drawer" aria-label="Close notifications">×</button>
    </div>
    <div class="drawer-body">
      <div class="inline-actions">
        <span class="muted-copy">${state.unreadCount} unread</span>
        <button type="button" class="secondary-button small-button" data-action="mark-all-read" ${state.unreadCount ? '' : 'disabled'}>Mark all as read</button>
      </div>
      ${items.length ? `<div class="notification-list">${items.map((item) => `
        <button type="button" class="notification-item ${item.is_read ? '' : 'is-unread'}" data-action="mark-notification-read" data-id="${item.id}">
          <span class="notification-item-heading"><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(statusLabel(item.notification_type))}</small></span>
          <span class="notification-item-message">${escapeHtml(item.message)}</span>
          <span class="notification-item-meta">${dateLabel(item.created_at)}${item.is_read ? ' · Read' : ' · Unread'}</span>
        </button>
      `).join('')}</div>` : '<div class="blank-card"><strong>No notifications yet.</strong><span>Your authorized Admin updates will appear here.</span></div>'}
    </div>`;
  openDrawer(content);
}

async function openNotificationsDrawer() {
  openDrawer('<div class="drawer-body"><div class="loading-state">Loading notifications…</div></div>');
  try {
    await refreshNotifications();
    renderNotificationDrawer();
  } catch (error) {
    openDrawer(`<div class="drawer-head"><div class="drawer-heading"><div class="eyebrow">Admin inbox</div><h2>Notifications</h2></div><button type="button" class="close-button" data-action="close-drawer" aria-label="Close notifications">×</button></div><div class="blank-card"><strong>Notifications could not load.</strong><span>${escapeHtml(error.message)}</span></div>`);
  }
}

function getOpenJobs() {
  return state.jobs.filter((job) => ['POSTED', 'APPLICATIONS', 'ACCEPTED', 'ADVANCE_PAID', 'STARTED', 'COMPLETION_PENDING'].includes(job.status));
}

function getCompletedJobs() {
  return state.jobs.filter((job) => ['COMPLETED', 'RESOLVED'].includes(job.status));
}

function getJobTimeline(job) {
  const steps = [
    { key: 'POSTED', label: 'Posted' },
    { key: 'APPLICATIONS', label: 'Applications' },
    { key: 'ACCEPTED', label: 'Accepted' },
    { key: 'ADVANCE_PAID', label: 'Advance' },
    { key: 'STARTED', label: 'Started' },
    { key: 'COMPLETION_PENDING', label: 'Evidence' },
    { key: 'COMPLETED', label: 'Completed' },
  ];

  const statusOrder = ['POSTED', 'APPLICATIONS', 'ACCEPTED', 'ADVANCE_PAID', 'STARTED', 'COMPLETION_PENDING', 'COMPLETED', 'CANCELLED', 'DISPUTED', 'RESOLVED'];
  const currentIndex = statusOrder.indexOf(job.status);

  return steps.map((step) => ({
    ...step,
    active: currentIndex >= statusOrder.indexOf(step.key),
  }));
}

function renderHomeView() {
  const openCount = getOpenJobs().length;
  const completedCount = getCompletedJobs().length;
  const unreadCount = state.notifications.filter((item) => !item.is_read).length;
  const complaintCount = state.complaints.filter((item) => item.status !== 'RESOLVED').length;

  return `
    <div class="page">
      <section class="hero-card">
        <div class="hero-copy">
          <div class="eyebrow">Cooperative operations</div>
          <h1>One cooperative view of the marketplace.</h1>
          <p>Rozgaar brings the live operational picture into view: where demand is rising, where workers are available, where disputes require attention, and where the cooperative needs to balance opportunity and supply.</p>
          <div class="hero-actions">
            <button type="button" class="primary-button" data-view="dashboard">Open dashboard</button>
            <button type="button" class="secondary-button" data-view="heatmap">Area / Heatmap</button>
            <button type="button" class="ghost-button" data-view="complaints">Support inbox</button>
          </div>
        </div>
        <div class="hero-visual">
          <div class="hero-visual-grid">
            <div class="signal-panel">
              <span>Open jobs</span>
              <strong>${openCount}</strong>
            </div>
            <div class="signal-panel">
              <span>Completed</span>
              <strong>${completedCount}</strong>
            </div>
            <div class="signal-panel">
              <span>Unread</span>
              <strong>${unreadCount}</strong>
            </div>
            <div class="signal-panel">
              <span>Support</span>
              <strong>${complaintCount}</strong>
            </div>
          </div>
        </div>
      </section>

      <section class="kpi-grid">
        <article class="metric-card is-strong">
          <span class="label">Purpose</span>
          <span class="value">Monitor</span>
          <span class="meta">Live platform health checks</span>
        </article>
        <article class="metric-card">
          <span class="label">Balance</span>
          <span class="value">Analyze</span>
          <span class="meta">Demand vs workforce</span>
        </article>
        <article class="metric-card is-coral">
          <span class="label">Resolve</span>
          <span class="value">Act</span>
          <span class="meta">Complaints + disputes</span>
        </article>
        <article class="metric-card">
          <span class="label">Improve</span>
          <span class="value">Learn</span>
          <span class="meta">Fair opportunity, payments</span>
        </article>
      </section>

      <section class="dashboard-layout">
        <div class="panel">
          <div class="panel-header">
            <h3>How Rozgaar works</h3>
          </div>
          <div class="panel-body">
            <div class="info-grid">
              <div class="info-box">
                <h4>Trust model</h4>
                <div class="list-line"><span>Job posting</span><strong>Consumer sets need</strong></div>
                <div class="list-line"><span>Matching</span><strong>Workers apply</strong></div>
                <div class="list-line"><span>Agreements</span><strong>Price + timing locked</strong></div>
                <div class="list-line"><span>Payment flow</span><strong>Simulated current system</strong></div>
              </div>
              <div class="info-box">
                <h4>Fair opportunity</h4>
                <div class="list-line"><span>Demand</span><strong>Observed by job flow</strong></div>
                <div class="list-line"><span>Supply</span><strong>Available worker signals</strong></div>
                <div class="list-line"><span>Balance</span><strong>Cooperative review</strong></div>
                <div class="list-line"><span>AI</span><strong>Not exposed here</strong></div>
              </div>
            </div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h3>Current operational highlights</h3>
          </div>
          <div class="panel-body">
            <ul class="summary-list">
              <li class="list-line"><span>Jobs in platform</span><strong>${state.jobs.length}</strong></li>
              <li class="list-line"><span>Open disputes</span><strong>${state.disputes.filter((item) => item.status !== 'RESOLVED').length}</strong></li>
              <li class="list-line"><span>Complaints requiring attention</span><strong>${state.complaints.filter((item) => item.status !== 'RESOLVED').length}</strong></li>
              <li class="list-line"><span>Simulated transaction value</span><strong>${money(state.paymentSummary)}</strong></li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderDashboardView() {
  const activeJobs = getOpenJobs().length;
  const completedCount = getCompletedJobs().length;
  const disputeCount = state.disputes.length;
  const complaintCount = state.complaints.filter((item) => item.status !== 'RESOLVED').length;
  const paymentIssues = state.payments.filter((item) => ['PENDING', 'FAILED', 'HELD', 'DISPUTED'].includes(item.status)).length;
  const unreadCount = state.notifications.filter((item) => !item.is_read).length;

  const attention = [
    { level: 'risk', title: 'Disputes', value: `${disputeCount} active`, detail: disputeCount ? 'Open cases are waiting on review and evidence checks.' : 'No active disputes are currently open.' },
    { level: 'warning', title: 'Payment issues', value: `${paymentIssues} flagged`, detail: paymentIssues ? 'Follow up on simulated payment status and held amounts.' : 'No payment issues are currently showing.' },
    { level: 'info', title: 'Outstanding work', value: `${activeJobs} operational jobs`, detail: 'Ongoing jobs continue to require coordination, evidence, or completion checks.' },
    { level: 'info', title: 'Support inbox', value: `${complaintCount} unresolved`, detail: complaintCount ? 'Items in the cooperative support inbox require review.' : 'No complaints are pending review.' },
  ];

  const recentActivity = [
    ...state.notifications.slice(0, 4).map((item) => ({ label: item.title, message: item.message, kind: item.is_read ? 'Read' : 'Unread' })),
    ...state.disputes.slice(0, 2).map((item) => ({ label: `Dispute: ${item.category}`, message: item.description, kind: item.status })),
    ...state.complaints.slice(0, 2).map((item) => ({ label: `Complaint: ${item.category}`, message: item.message, kind: item.status })),
  ].slice(0, 6);

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Operations</div>
          <h2>Rozgaar operations dashboard</h2>
        </div>
        <button type="button" class="secondary-button" data-action="refresh-data">Refresh live data</button>
      </div>

      <section class="kpi-grid">
        <article class="metric-card is-strong">
          <span class="label">Total workers</span>
          <span class="value">Data needed</span>
          <span class="meta">No worker directory endpoint exposed</span>
        </article>
        <article class="metric-card">
          <span class="label">Active workers</span>
          <span class="value">Data needed</span>
          <span class="meta">Requires workforce analytics</span>
        </article>
        <article class="metric-card">
          <span class="label">Total consumers</span>
          <span class="value">Data needed</span>
          <span class="meta">No consumer directory endpoint</span>
        </article>
        <article class="metric-card is-coral">
          <span class="label">Open jobs</span>
          <span class="value">${activeJobs}</span>
          <span class="meta">Current live job volume</span>
        </article>
        <article class="metric-card">
          <span class="label">Completed jobs</span>
          <span class="value">${completedCount}</span>
          <span class="meta">Closed by state</span>
        </article>
        <article class="metric-card">
          <span class="label">Disputes</span>
          <span class="value">${disputeCount}</span>
          <span class="meta">Open or under review</span>
        </article>
        <article class="metric-card">
          <span class="label">Transaction value</span>
          <span class="value">${money(state.paymentSummary)}</span>
          <span class="meta">Simulated transactions</span>
        </article>
        <article class="metric-card">
          <span class="label">Workforce utilization</span>
          <span class="value">Data needed</span>
          <span class="meta">Requires analytics backend</span>
        </article>
      </section>

      <section class="dashboard-layout">
        <div class="panel">
          <div class="panel-header">
            <h3>Attention required</h3>
          </div>
          <div class="panel-body">
            <ul class="attention-list">
              ${attention.map((item) => `
                <li class="attention-item">
                  <div class="alert-content">
                    <strong>${escapeHtml(item.title)}</strong>
                    <span>${escapeHtml(item.value)}</span>
                    <small>${escapeHtml(item.detail)}</small>
                  </div>
                  <span class="alert-pill ${item.level}">${escapeHtml(item.level === 'risk' ? 'Action' : item.level === 'warning' ? 'Review' : 'Monitor')}</span>
                </li>
              `).join('')}
            </ul>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h3>Marketplace signal</h3>
          </div>
          <div class="panel-body">
            <div class="info-grid">
              <div class="info-box">
                <h4>Demand</h4>
                <div class="list-line"><span>Jobs posted</span><strong>${state.jobs.length}</strong></div>
                <div class="list-line"><span>Urgent jobs</span><strong>${state.jobs.filter((job) => job.emergency_level === 'URGENT').length}</strong></div>
                <div class="list-line"><span>Need in a day</span><strong>${state.jobs.filter((job) => job.emergency_level === 'NEEDED_IN_A_DAY').length}</strong></div>
              </div>
              <div class="info-box">
                <h4>Supply</h4>
                <div class="list-line"><span>Unread alerts</span><strong>${unreadCount}</strong></div>
                <div class="list-line"><span>Open support</span><strong>${complaintCount}</strong></div>
                <div class="list-line"><span>Resolved</span><strong>${state.jobs.filter((job) => job.status === 'RESOLVED').length}</strong></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section class="dashboard-layout">
        <div class="panel">
          <div class="panel-header">
            <h3>Recent activity</h3>
          </div>
          <div class="panel-body">
            <ul class="activity-list">
              ${recentActivity.map((item) => `
                <li class="activity-item">
                  <span class="dot"></span>
                  <div>
                    <strong>${escapeHtml(item.label)}</strong>
                    <span>${escapeHtml(item.message)}</span>
                    <small>${escapeHtml(item.kind)}</small>
                  </div>
                </li>
              `).join('') || '<li class="muted-copy">No recent activity available.</li>'}
            </ul>
          </div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h3>Operational categories</h3>
          </div>
          <div class="panel-body">
            <div class="tag-row">
              ${Array.from(new Set(state.jobs.map((job) => job.category))).slice(0, 10).map((category) => `<span class="tag is-moss">${escapeHtml(category)}</span>`).join('') || '<span class="tag is-muted">No job categories available</span>'}
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}

function renderHeatmapView() {
  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Area / heatmap</div>
          <h2>Supply versus demand</h2>
        </div>
      </div>

      <div class="filters-block admin-heatmap-filters">
        <div class="filter-group">
          <label for="admin-city">City / area</label>
          <input id="admin-city" placeholder="Kolkata" />
        </div>
        <div class="filter-group">
          <label for="admin-category">Skill / category</label>
          <input id="admin-category" placeholder="All categories" />
        </div>
        <div class="filter-group">
          <label for="admin-region">Region</label>
          <select id="admin-region">
            <option value="">All returned regions</option>
          </select>
        </div>
        <button type="button" class="secondary-button" data-action="load-admin-heatmap">Load regional data</button>
        <button type="button" class="ghost-button" data-action="reset-admin-map">Reset view</button>
      </div>

      <section class="map-shell">
        <div class="map-panel">
          <div id="admin-heatmap-state" class="blank-card">
            <strong>Loading real regional data.</strong>
            <p>Worker locations are rounded into privacy-safe regions. Exact coordinates are never exposed.</p>
          </div>
          <div id="admin-real-map-wrap" class="admin-map-frame"></div>
        </div>

        <aside class="panel">
          <div class="panel-header">
            <h3>Regional detail</h3>
          </div>
          <div class="panel-body">
            <div class="legend">
              <div class="legend-item"><span class="swatch high-demand"></span>Shortage / underserved</div>
              <div class="legend-item"><span class="swatch balanced"></span>Balanced</div>
              <div class="legend-item"><span class="swatch worker-heavy"></span>Oversupplied</div>
            </div>
            <div id="admin-region-rows"></div>
          </div>
        </aside>
      </section>
    </div>
  `;
}

function bindHeatmapControls() {
  document.querySelector('[data-action="load-admin-heatmap"]')?.addEventListener('click', loadAdminHeatmapData);
}

function readAdminHeatmapState() {
  try {
    const saved = sessionStorage.getItem(ADMIN_HEATMAP_SESSION_KEY);
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

function writeAdminHeatmapState(data) {
  try {
    sessionStorage.setItem(ADMIN_HEATMAP_SESSION_KEY, JSON.stringify(data));
  } catch {
    // Session storage is optional; the live map remains usable if unavailable.
  }
}

function restoreAdminHeatmapState() {
  const saved = readAdminHeatmapState();
  if (!saved || !Array.isArray(saved.regions) || !saved.searchedLocation) return false;

  const cityInput = document.getElementById('admin-city');
  const categoryInput = document.getElementById('admin-category');
  const regionSelect = document.getElementById('admin-region');
  const stateNode = document.getElementById('admin-heatmap-state');
  const mapWrap = document.getElementById('admin-real-map-wrap');
  const rowsWrap = document.getElementById('admin-region-rows');
  if (!cityInput || !categoryInput || !regionSelect || !stateNode || !mapWrap || !rowsWrap) return false;

  cityInput.value = saved.city || saved.searchedLocation;
  categoryInput.value = saved.category || '';
  regionSelect.innerHTML = '<option value="">All returned regions</option>' + saved.regions.map((region) => `<option value="${escapeHtml(region.region)}">${escapeHtml(region.region)}</option>`).join('');
  regionSelect.value = saved.selectedRegion || '';
  stateNode.querySelector('strong').textContent = saved.stateTitle;
  stateNode.querySelector('p').textContent = saved.stateMessage;

  const visibleRegions = saved.selectedRegion ? saved.regions.filter((region) => region.region === saved.selectedRegion) : saved.regions;
  mapWrap.innerHTML = renderRegionalMap(visibleRegions);
  initializeAdminMap(visibleRegions, saved.searchedCoordinates, saved.viewport);
  rowsWrap.innerHTML = visibleRegions.length ? renderRegionalRows(visibleRegions) : '<div class="admin-data-needed">No regional locations were resolved for this selection.</div>';
  return true;
}

async function loadAdminHeatmapData() {
  const city = document.getElementById('admin-city')?.value.trim() || '';
  const category = document.getElementById('admin-category')?.value.trim() || '';
  const stateNode = document.getElementById('admin-heatmap-state');
  const mapWrap = document.getElementById('admin-real-map-wrap');
  const rowsWrap = document.getElementById('admin-region-rows');

  if (!stateNode || !mapWrap || !rowsWrap) return;

  try {
    const query = new URLSearchParams();
    if (city) query.set('city', city);
    if (category) query.set('category', category);
    const queryString = query.toString() ? `?${query.toString()}` : '';
    const payload = await api(`/location-intelligence/admin${queryString}`);
    const list = Array.isArray(payload) ? payload : [payload].filter(Boolean);
    const rawRegions = list.flatMap((item) => Array.isArray(item?.regions) ? item.regions : []);
    const regions = await normalizeMapRegions(rawRegions);
    const searchedLocation = city || list[0]?.location?.location || '';
    const searchedCoordinates = searchedLocation ? await resolveAdminSearchLocation(searchedLocation) : null;

    stateNode.querySelector('strong').textContent = regions.length ? `${regions.length} real regions in view.` : searchedCoordinates ? 'No regional intelligence available for this selection yet.' : 'Location could not be resolved.';
    stateNode.querySelector('p').textContent = regions.length
      ? 'Marker size reflects worker concentration. Color and labels use backend supply-demand aggregates.'
      : searchedCoordinates ? `0 regional locations resolved for ${searchedLocation}. The geographic map remains available without fabricated markers.` : 'Enter a recognizable city, state, or area to resolve the geographic map.';

    const regionSelect = document.getElementById('admin-region');
    if (regionSelect) {
      const selectedRegion = regionSelect.value;
      regionSelect.innerHTML = '<option value="">All returned regions</option>' + regions.map((region) => `<option value="${escapeHtml(region.region)}">${escapeHtml(region.region)}</option>`).join('');
      if (regions.some((region) => region.region === selectedRegion)) regionSelect.value = selectedRegion;
    }
    const selectedRegion = regionSelect?.value || '';
    const visibleRegions = selectedRegion ? regions.filter((region) => region.region === selectedRegion) : regions;
    mapWrap.innerHTML = renderRegionalMap(visibleRegions);
    initializeAdminMap(visibleRegions, searchedCoordinates);
    rowsWrap.innerHTML = visibleRegions.length ? renderRegionalRows(visibleRegions) : '<div class="admin-data-needed">No regional locations were resolved for this selection.</div>';
    writeAdminHeatmapState({
      city,
      category,
      selectedRegion,
      searchedLocation,
      searchedCoordinates,
      regions,
      stateTitle: stateNode.querySelector('strong').textContent,
      stateMessage: stateNode.querySelector('p').textContent,
      viewport: searchedCoordinates ? { center: searchedCoordinates, zoom: regions.length ? 14 : 7 } : null,
    });
  } catch (error) {
    stateNode.querySelector('strong').textContent = 'Regional data unavailable.';
    stateNode.querySelector('p').textContent = error.message || 'The backend did not return regional intelligence for this view.';
    mapWrap.innerHTML = '<div class="admin-data-needed">No regional intelligence available for this selection yet.</div>';
    rowsWrap.innerHTML = '<div class="admin-data-needed">No regional rows returned for these filters.</div>';
  }
}

function renderRegionalMap(regions) {
  return '<div id="admin-leaflet-map" class="leaflet-map" aria-label="Regional supply and demand geographic map"></div>';
}

async function resolveAdminSearchLocation(location) {
  try {
    const response = await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q=${encodeURIComponent(location)}`, { headers: { Accept: 'application/json' } });
    const result = (await response.json())[0];
    if (result && Number.isFinite(Number(result.lat)) && Number.isFinite(Number(result.lon))) return [Number(result.lat), Number(result.lon)];
  } catch {
    return null;
  }
  return null;
}

function canonicalizeRegionKey(value) {
  const normalized = String(value || '').trim().replace(/[^a-z0-9]+/gi, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
  return normalized || 'regional area';
}

function canonicalizeRegionLabel(value) {
  const key = canonicalizeRegionKey(value);
  if (!key || key === 'regional area') return 'Regional area';
  const tokens = key.split(' ');
  const cityNames = new Set(['ahmedabad', 'bangalore', 'chennai', 'delhi', 'gurugram', 'hyderabad', 'jaipur', 'kolkata', 'mumbai', 'noida', 'pune', 'thane']);
  if (tokens.length > 1 && cityNames.has(tokens[tokens.length - 1])) {
    const area = tokens.slice(0, -1).map((token) => token.charAt(0).toUpperCase() + token.slice(1)).join(' ');
    const city = tokens[tokens.length - 1].charAt(0).toUpperCase() + tokens[tokens.length - 1].slice(1);
    return `${area}, ${city}`;
  }
  return tokens.map((token) => token.charAt(0).toUpperCase() + token.slice(1)).join(' ');
}

async function normalizeMapRegions(rawRegions) {
  const grouped = new Map();

  rawRegions.filter((region) => region && typeof region === 'object').forEach((region) => {
    const latitude = Number(region.latitude);
    const longitude = Number(region.longitude);
    const label = canonicalizeRegionLabel(region.region || '');
    const key = canonicalizeRegionKey(label);
    if (!key || !Number.isFinite(latitude) || !Number.isFinite(longitude)) return;

    const current = grouped.get(key) || {
      ...region,
      region: label,
      latitude,
      longitude,
      worker_count: 0,
      available_worker_count: 0,
      relevant_job_count: 0,
      active_demand: 0,
      ongoing_job_count: 0,
      completed_job_count: 0,
      coordinateSource: null,
      records: [],
    };

    current.records.push(region);
    current.worker_count += Number(region.worker_count || 0);
    current.available_worker_count += Number(region.available_worker_count || 0);
    current.relevant_job_count += Number(region.relevant_job_count || 0);
    current.active_demand += Number(region.active_demand || 0);
    current.ongoing_job_count += Number(region.ongoing_job_count || 0);
    current.completed_job_count += Number(region.completed_job_count || 0);

    const candidateScore = (Number(region.active_demand) || 0) * 5 + (Number(region.worker_count) || 0) * 2 + (Number(region.relevant_job_count) || 0);
    const currentScore = current.coordinateSource ? ((Number(current.coordinateSource.active_demand) || 0) * 5 + (Number(current.coordinateSource.worker_count) || 0) * 2 + (Number(current.coordinateSource.relevant_job_count) || 0)) : -Infinity;
    if (!current.coordinateSource || candidateScore > currentScore) {
      current.latitude = latitude;
      current.longitude = longitude;
      current.coordinateSource = region;
      current.region = label;
    }

    grouped.set(key, current);
  });

  return [...grouped.values()].map((region) => {
    const ratio = region.available_worker_count ? Number((region.active_demand / region.available_worker_count).toFixed(2)) : null;
    const state = region.active_demand && !region.available_worker_count ? 'UNDERSERVED' : ratio && ratio > 1 ? 'SHORTAGE' : region.available_worker_count && ratio !== null && ratio < 0.5 ? 'OVERSUPPLIED' : 'BALANCED';
    const normalized = { ...region, latitude: Number(region.latitude), longitude: Number(region.longitude), supply_demand_ratio: ratio, state, opportunity_score: Number(Math.min(100, region.active_demand / Math.max(region.available_worker_count, 1) * 50).toFixed(1)) };
    delete normalized.records;
    delete normalized.coordinateSource;
    return normalized;
  });
}

async function resolveCanonicalRegionCoordinates(regionName, records) {
  const valid = records.filter((record) => Number.isFinite(Number(record.latitude)) && Number.isFinite(Number(record.longitude)));
  if (!valid.length) return [null, null];

  const chosen = valid.reduce((best, record) => {
    const score = (Number(record.active_demand) || 0) * 5 + (Number(record.worker_count) || 0) * 2 + (Number(record.relevant_job_count) || 0);
    return score > best.score ? { score, record } : best;
  }, { score: -Infinity, record: valid[0] });

  return [Number(chosen.record.latitude), Number(chosen.record.longitude)];
}

function initializeAdminMap(regions, searchedCoordinates = null, viewport = null) {
  const mapNode = document.getElementById('admin-leaflet-map');
  if (!mapNode) return;
  if (!window.L) {
    if (!document.querySelector('link[data-leaflet-css]')) {
      const style = document.createElement('link');
      style.rel = 'stylesheet';
      style.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      style.dataset.leafletCss = 'true';
      document.head.appendChild(style);
    }
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.onload = () => initializeAdminMap(regions, searchedCoordinates, viewport);
    document.head.appendChild(script);
    return;
  }
  if (state.adminMap) state.adminMap.remove();
  state.adminMap = window.L.map(mapNode, { zoomControl: true, scrollWheelZoom: true });
  window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(state.adminMap);

  const fallbackLayers = [];
  if (!regions.length && searchedCoordinates) {
    const centerLat = Number(searchedCoordinates[0]);
    const centerLng = Number(searchedCoordinates[1]);
    for (let index = 0; index < 5; index += 1) {
      const angle = (index / 5) * Math.PI * 2;
      const latitude = centerLat + Math.cos(angle) * 0.025;
      const longitude = centerLng + Math.sin(angle) * 0.03;
      const layer = window.L.circleMarker([latitude, longitude], {
        radius: 8,
        color: '#d7d7d7',
        fillColor: '#f0f0f0',
        fillOpacity: 0.8,
        weight: 1,
      })
        .bindPopup('<strong>No active jobs</strong><br>Sample coverage area')
        .bindTooltip('No active jobs', { direction: 'top', sticky: true })
        .addTo(state.adminMap);
      fallbackLayers.push(layer);
    }
  }

  const layers = regions.map((region) => {
    const color = region.state === 'OVERSUPPLIED' ? '#d59b27' : region.state === 'BALANCED' ? '#315c4c' : '#d9684f';
    const layer = window.L.circle([region.latitude, region.longitude], { radius: 0, color, fillColor: color, fillOpacity: 0.2, weight: 2 })
      .bindPopup(`<strong>${escapeHtml(region.region)}</strong><br>Workers: ${region.worker_count}<br>Available: ${region.available_worker_count}<br>Demand: ${region.active_demand}<br>Status: ${statusLabel(region.state)}`)
      .bindTooltip(escapeHtml(region.region), { direction: 'top', sticky: true })
      .addTo(state.adminMap);
    return layer;
  });
  state.adminMapLayers = [...layers, ...fallbackLayers];
  const saveViewport = () => {
    const saved = readAdminHeatmapState();
    if (!saved) return;
    const center = state.adminMap.getCenter();
    saved.viewport = { center: [center.lat, center.lng], zoom: state.adminMap.getZoom() };
    writeAdminHeatmapState(saved);
  };
  const updateMarkerSizes = () => {
    const zoom = state.adminMap.getZoom();
    const radius = Math.max(220, Math.min(900, 420 * Math.pow(2, zoom - 12)));
    layers.forEach((layer) => layer.setRadius(radius));
  };
  state.adminMap.on('zoomend', updateMarkerSizes);
  state.adminMap.on('moveend', saveViewport);
  updateMarkerSizes();
  state.adminMapBounds = regions.length ? window.L.latLngBounds(regions.map((region) => [region.latitude, region.longitude])) : null;
  if (viewport?.center && Number.isFinite(viewport.zoom)) state.adminMap.setView(viewport.center, viewport.zoom);
  else if (state.adminMapBounds?.isValid()) resetAdminMapView();
  else if (searchedCoordinates) state.adminMap.setView(searchedCoordinates, 7);
  else if (fallbackLayers.length) state.adminMap.setView([fallbackLayers[0]._latlng.lat, fallbackLayers[0]._latlng.lng], 7);
}

function resetAdminMapView() {
  if (!state.adminMap || !state.adminMapBounds?.isValid()) return;
  state.adminMap.fitBounds(state.adminMapBounds.pad(0.25), { maxZoom: 14 });
}

function renderRegionalRows(regions) {
  return regions.length ? `<div class="admin-region-list">${regions.map(region => `<div class="admin-region-row"><div><strong>${escapeHtml(region.region)}</strong><small>${region.worker_count} workers · ${region.available_worker_count} available · ${region.active_demand} active demand</small></div><span class="status-badge ${region.state === 'OVERSUPPLIED' ? 'warn' : region.state === 'BALANCED' ? 'moss' : 'coral'}">${escapeHtml(region.state)}</span></div>`).join('')}</div>` : '<div class="admin-data-needed">No regional rows returned for these filters.</div>';
}

function renderJobsView() {
  const rows = state.jobs.map((job) => `
    <tr>
      <td>
        <strong>${escapeHtml(job.title)}</strong><br>
        <span class="muted-copy">${escapeHtml(job.category)} · ${escapeHtml(job.location)}</span>
      </td>
      <td>${escapeHtml(job.status)}</td>
      <td>${escapeHtml(job.emergency_level)}</td>
      <td>${dateLabel(job.scheduled_date)}</td>
      <td>${money(job.minimum_platform_cost)}</td>
      <td>${escapeHtml(job.required_worker_count)}</td>
      <td><button type="button" class="link-button" data-action="view-job" data-id="${job.id}">Open</button></td>
    </tr>
  `).join('');

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Jobs</div>
          <h2>Operational jobs</h2>
        </div>
      </div>

      <div class="filters-block">
        <div class="filter-group">
          <label for="admin-job-status">Status</label>
          <select id="admin-job-status">
            <option value="">All live states</option>
            <option value="POSTED">POSTED</option>
            <option value="APPLICATIONS">APPLICATIONS</option>
            <option value="ACCEPTED">ACCEPTED</option>
            <option value="ADVANCE_PAID">ADVANCE_PAID</option>
            <option value="STARTED">STARTED</option>
            <option value="COMPLETION_PENDING">COMPLETION_PENDING</option>
            <option value="COMPLETED">COMPLETED</option>
            <option value="CANCELLED">CANCELLED</option>
            <option value="DISPUTED">DISPUTED</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>
        </div>
        <div class="filter-group">
          <label for="admin-job-activity">Activity</label>
          <select id="admin-job-activity">
            <option value="">Current list</option>
            <option value="RECENT">Recently updated</option>
            <option value="ACTIVE">Active work</option>
            <option value="COMPLETED">Completed</option>
          </select>
        </div>
      </div>

      <div class="table-shell">
        <table class="data-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Status</th>
              <th>Urgency</th>
              <th>Schedule</th>
              <th>Minimum cost</th>
              <th>Workers</th>
              <th>View</th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan="7"><div class="blank-card"><strong>No operational jobs match the current filters.</strong><span class="muted-copy">The job list will populate when jobs are posted.</span></div></td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function bindJobsFilters() {
  const status = document.getElementById('admin-job-status');
  const activity = document.getElementById('admin-job-activity');
  const body = document.querySelector('.data-table tbody');
  if (!status || !activity || !body) return;

  const renderFilteredRows = () => {
    const selectedStatus = status.value;
    const selectedActivity = activity.value;
    let jobs = state.jobs.filter((job) => !selectedStatus || job.status === selectedStatus);

    if (selectedActivity === 'ACTIVE') {
      jobs = jobs.filter((job) => ['ACCEPTED', 'ADVANCE_PAID', 'STARTED', 'COMPLETION_PENDING', 'DISPUTED'].includes(job.status));
    } else if (selectedActivity === 'COMPLETED') {
      jobs = jobs.filter((job) => ['COMPLETED', 'RESOLVED'].includes(job.status));
    } else if (selectedActivity === 'RECENT') {
      const ordered = [...jobs].sort((first, second) => new Date(second.updated_at || second.created_at || 0) - new Date(first.updated_at || first.created_at || 0));
      jobs = ordered.slice(0, 1);
    }

    body.innerHTML = jobs.length ? jobs.map((job) => `
      <tr>
        <td><strong>${escapeHtml(job.title)}</strong><br><span class="muted-copy">${escapeHtml(job.category)} · ${escapeHtml(job.location)}</span></td>
        <td>${escapeHtml(job.status)}</td>
        <td>${escapeHtml(job.emergency_level)}</td>
        <td>${dateLabel(job.scheduled_date)}</td>
        <td>${money(job.minimum_platform_cost)}</td>
        <td>${escapeHtml(job.required_worker_count)}</td>
        <td><button type="button" class="link-button" data-action="view-job" data-id="${job.id}">Open</button></td>
      </tr>
    `).join('') : '<tr><td colspan="7"><div class="blank-card"><strong>No jobs match this status.</strong><span class="muted-copy">Try another status or activity filter.</span></div></td></tr>';
  };

  status.addEventListener('change', renderFilteredRows);
  activity.addEventListener('change', renderFilteredRows);
}

function renderWorkforceView() {
  const active = state.jobs.filter((job) => ['ACCEPTED', 'ADVANCE_PAID', 'STARTED', 'COMPLETION_PENDING'].includes(job.status));
  const urgent = state.jobs.filter((job) => job.emergency_level === 'URGENT').length;

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Workforce</div>
          <h2>Workforce balance</h2>
        </div>
      </div>

      <section class="kpi-grid">
        <article class="metric-card is-strong">
          <span class="label">Operational jobs</span>
          <span class="value">${active.length}</span>
          <span class="meta">Jobs currently moving</span>
        </article>
        <article class="metric-card">
          <span class="label">Urgent demand</span>
          <span class="value">${urgent}</span>
          <span class="meta">High-priority requests</span>
        </article>
        <article class="metric-card">
          <span class="label">Balance</span>
          <span class="value">Data needed</span>
          <span class="meta">Requires workforce analytics</span>
        </article>
        <article class="metric-card is-coral">
          <span class="label">Fair opportunity</span>
          <span class="value">Monitor</span>
          <span class="meta">Human oversight remains the signal</span>
        </article>
      </section>

      <div class="blank-card">
        <div class="eyebrow">Unavailable data state</div>
        <strong>Workforce analytics are not exposed by the current backend.</strong>
        <p>The admin UI intentionally does not fabricate worker density, assignment recommendations, or demand forecasts. Current job volumes and operational demand are shown instead.</p>
      </div>
    </div>
  `;
}

function renderDisputesView() {
  const rows = state.disputes.map((item) => `
    <tr>
      <td>${escapeHtml(item.category || 'General')}</td>
      <td>${escapeHtml(item.status)}</td>
      <td>${dateLabel(item.created_at)}</td>
      <td>${escapeHtml(item.job_id || '—')}</td>
      <td><button type="button" class="link-button" data-action="view-dispute" data-id="${item.id}">Review</button></td>
    </tr>
  `).join('');

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Disputes</div>
          <h2>Dispute management</h2>
        </div>
      </div>

      <div class="table-shell">
        <table class="data-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Status</th>
              <th>Opened</th>
              <th>Job</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan="5"><div class="blank-card"><strong>No active disputes.</strong><span class="muted-copy">Disputes will appear here when raised and assigned for review.</span></div></td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderPaymentsView() {
  const rows = state.payments.map((item) => `
    <tr>
      <td>${escapeHtml(item.job_id)}</td>
      <td>${money(item.agreed_amount)}</td>
      <td>${money(item.advance_amount)}</td>
      <td>${money(item.final_amount)}</td>
      <td><span class="status-badge ${resolveStatusClass(item.status)}">${escapeHtml(item.status)}</span></td>
      <td>${escapeHtml(item.payment_type)}</td>
    </tr>
  `).join('');

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Payments</div>
          <h2>Payment monitoring</h2>
        </div>
      </div>

      <section class="kpi-grid">
        <article class="metric-card is-strong">
          <span class="label">Simulated value</span>
          <span class="value">${money(state.paymentSummary)}</span>
          <span class="meta">Current monitored total</span>
        </article>
        <article class="metric-card">
          <span class="label">Held/disputed</span>
          <span class="value">${state.payments.filter((item) => ['HELD', 'DISPUTED'].includes(item.status)).length}</span>
          <span class="meta">Needs review</span>
        </article>
        <article class="metric-card">
          <span class="label">Pending</span>
          <span class="value">${state.payments.filter((item) => item.status === 'PENDING').length}</span>
          <span class="meta">Advance or final payment</span>
        </article>
        <article class="metric-card is-coral">
          <span class="label">Status</span>
          <span class="value">Readonly</span>
          <span class="meta">No real payment provider</span>
        </article>
      </section>

      <div class="table-shell">
        <table class="data-table">
          <thead>
            <tr>
              <th>Job</th>
              <th>Agreed</th>
              <th>Advance</th>
              <th>Final</th>
              <th>Status</th>
              <th>Type</th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan="6"><div class="blank-card"><strong>No payment records.</strong><span class="muted-copy">The payment list will populate as agreements are created.</span></div></td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderComplaintsView() {
  const rows = state.complaints.map((item) => `
    <tr>
      <td>${escapeHtml(item.category)}</td>
      <td>${escapeHtml(item.status)}</td>
      <td>${escapeHtml(item.reporter_role || 'UNKNOWN')}</td>
      <td>${escapeHtml(item.job_id || '—')}</td>
      <td><button type="button" class="link-button" data-action="view-complaint" data-id="${item.id}">Review</button></td>
    </tr>
  `).join('');

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Complaints</div>
          <h2>Support inbox</h2>
        </div>
      </div>

      <div class="table-shell">
        <table class="data-table">
          <thead>
            <tr>
              <th>Category</th>
              <th>Status</th>
              <th>Reporter</th>
              <th>Job</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan="5"><div class="blank-card"><strong>No complaints require attention.</strong><span class="muted-copy">The support inbox is clear.</span></div></td></tr>`}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderAnalyticsView() {
  const categoryCounts = {};
  for (const job of state.jobs) {
    categoryCounts[job.category] = (categoryCounts[job.category] || 0) + 1;
  }

  const topCategories = Object.entries(categoryCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);

  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">Analytics</div>
          <h2>Operational insights</h2>
        </div>
      </div>

      <section class="kpi-grid">
        <article class="metric-card is-strong">
          <span class="label">Jobs posted</span>
          <span class="value">${state.jobs.length}</span>
          <span class="meta">Live job count</span>
        </article>
        <article class="metric-card">
          <span class="label">Completed</span>
          <span class="value">${getCompletedJobs().length}</span>
          <span class="meta">Closed jobs</span>
        </article>
        <article class="metric-card">
          <span class="label">Cancelled</span>
          <span class="value">${state.jobs.filter((job) => job.status === 'CANCELLED').length}</span>
          <span class="meta">Cancelled on platform</span>
        </article>
        <article class="metric-card is-coral">
          <span class="label">Disputed</span>
          <span class="value">${state.disputes.length}</span>
          <span class="meta">Live review cases</span>
        </article>
      </section>

      <div class="panel">
        <div class="panel-header">
          <h3>Demand categories</h3>
        </div>
        <div class="panel-body">
          <div class="tag-row">
            ${topCategories.length ? topCategories.map(([name, count]) => `<span class="tag is-moss">${escapeHtml(name)} · ${count}</span>`).join('') : '<span class="tag is-muted">Job category data not available</span>'}
          </div>
        </div>
      </div>
    </div>
  `;
}

function renderUsersView() {
  return `
    <div class="page">
      <div class="section-header">
        <div>
          <div class="eyebrow">User management</div>
          <h2>Workers and consumers</h2>
        </div>
      </div>
      <div class="filters-row">
        <input id="admin-user-search" placeholder="Search name, email, or phone" aria-label="Search users">
        <select id="admin-user-role" aria-label="Filter role"><option value="">All roles</option><option value="WORKER">Workers</option><option value="CONSUMER">Consumers</option></select>
        <select id="admin-user-status" aria-label="Filter status"><option value="">All statuses</option><option value="ACTIVE">Active</option><option value="SUSPENDED">Suspended</option></select>
        <button class="secondary-button" data-action="refresh-users">Refresh</button>
      </div>
      <div id="admin-users-list" class="blank-card">Loading users...</div>
      <div class="pagination-row"><button class="secondary-button" data-action="users-prev">Previous</button><span id="admin-users-page">Page 1</span><button class="secondary-button" data-action="users-next">Next</button></div>
    </div>
  `;
}

async function loadUsersView() {
  const search = $('#admin-user-search')?.value.trim() || '';
  const role = $('#admin-user-role')?.value || '';
  const accountStatus = $('#admin-user-status')?.value || '';
  const params = new URLSearchParams({ page: String(state.usersPage), page_size: String(state.usersPageSize) });
  if (search) params.set('search', search);
  if (role) params.set('role', role);
  if (accountStatus) params.set('account_status', accountStatus);
  try {
    const data = await api(`/admin/users?${params}`);
    state.users = data.items || [];
    state.usersTotal = data.total || 0;
    const list = $('#admin-users-list');
    if (list) list.innerHTML = state.users.length ? state.users.map(user => `<button class="list-row" data-action="open-admin-user" data-id="${user.id}"><span><strong>${escapeHtml(user.name)}</strong><small>${escapeHtml(user.email || user.phone)} · ${escapeHtml(user.role)} · ${escapeHtml(user.account_status)}</small></span><span>${user.rating_average ? `★ ${Number(user.rating_average).toFixed(1)} (${user.review_count})` : 'No reviews'}</span></button>`).join('') : '<div class="empty-state">No users match the current filters.</div>';
    if ($('#admin-users-page')) $('#admin-users-page').textContent = `Page ${data.page} · ${data.total} users`;
    bindUserFilters();
  } catch (error) { const list = $('#admin-users-list'); if (list) list.textContent = error.message; }
}

function bindUserFilters() { ['admin-user-search', 'admin-user-role', 'admin-user-status'].forEach(id => { const node = $(`#${id}`); if (node && !node.dataset.bound) { node.dataset.bound = 'true'; node.addEventListener('change', () => { state.usersPage = 1; loadUsersView(); }); if (id === 'admin-user-search') node.addEventListener('keydown', event => { if (event.key === 'Enter') { state.usersPage = 1; loadUsersView(); } }); } }); }

async function openAdminUser(userId) { const user = await api(`/admin/users/${userId}`); openDrawer(`<div class="drawer-head"><div class="eyebrow">User detail</div><h2>${escapeHtml(user.name)}</h2><button type="button" class="close-button" data-action="close-drawer" aria-label="Close">×</button></div><div class="drawer-body"><div class="detail-grid"><div class="detail-box"><span>Role</span><strong>${escapeHtml(user.role)}</strong></div><div class="detail-box"><span>Status</span><strong>${escapeHtml(user.account_status)}</strong></div><div class="detail-box"><span>Email</span><strong>${escapeHtml(user.email || 'Not listed')}</strong></div><div class="detail-box"><span>Rating</span><strong>${user.rating_average ? `${Number(user.rating_average).toFixed(1)} (${user.review_count})` : 'No reviews'}</strong></div><div class="detail-box"><span>Jobs</span><strong>${user.jobs_count}</strong></div><div class="detail-box"><span>Applications</span><strong>${user.applications_count}</strong></div></div></div>`, 'User detail'); }

function resolveStatusClass(status) {
  switch (status) {
    case 'COMPLETED':
      return 'moss';
    case 'PENDING':
      return 'warn';
    case 'FAILED':
    case 'DISPUTED':
    case 'HELD':
      return 'coral';
    default:
      return 'muted';
  }
}

async function openJobDrawer(jobId) {
  const job = state.jobs.find((item) => item.id === jobId);
  if (!job) return;

  const notes = [
    { label: 'Category', value: job.category },
    { label: 'Location', value: job.location },
    { label: 'Urgency', value: job.emergency_level },
    { label: 'Workers needed', value: `${job.required_worker_count}` },
    { label: 'Contract value', value: money(job.minimum_platform_cost) },
    { label: 'Status', value: job.status },
  ];

  const timeline = getJobTimeline(job);

  openDrawer(`
    <div class="drawer-head">
      <div class="drawer-heading">
        <div class="eyebrow">Job detail</div>
        <h2>${escapeHtml(job.title)}</h2>
      </div>
      <button type="button" class="close-button" data-action="close-drawer" aria-label="Close job detail">×</button>
    </div>
    <div class="drawer-body">
      <div class="drawer-section">
        <div class="detail-grid">
          ${notes.map((item) => `
            <div class="detail-box">
              <span>${escapeHtml(item.label)}</span>
              <strong>${escapeHtml(item.value)}</strong>
            </div>
          `).join('')}
        </div>
      </div>

      <div class="drawer-section">
        <h4>Timeline</h4>
        <div class="timeline">
          ${timeline.map((step) => `
            <div class="timeline-item ${step.active ? 'is-active' : ''}">
              <strong>${escapeHtml(step.label)}</strong>
              ${step.active ? 'Observed in the current lifecycle.' : 'Pending / not yet reached.'}
            </div>
          `).join('')}
        </div>
      </div>

      <div class="drawer-section">
        <h4>Job description</h4>
        <p>${escapeHtml(job.description || 'No description was provided.')}</p>
      </div>
    </div>
  `);
}

async function openDisputeDrawer(disputeId) {
  const dispute = state.disputes.find((item) => item.id === disputeId);
  if (!dispute) return;

  try {
    const detail = await api(`/admin/disputes/${disputeId}`);
    openDrawer(`
      <div class="drawer-head">
        <div class="drawer-heading">
          <div class="eyebrow">Dispute review</div>
          <h2>${escapeHtml(detail.category || 'Dispute')}</h2>
        </div>
        <button type="button" class="close-button" data-action="close-drawer" aria-label="Close dispute review">×</button>
      </div>
      <div class="drawer-body">
        <div class="drawer-section">
          <div class="detail-grid">
            <div class="detail-box"><span>Job</span><strong>${escapeHtml(detail.job_id || '—')}</strong></div>
            <div class="detail-box"><span>Status</span><strong>${escapeHtml(detail.status)}</strong></div>
            <div class="detail-box"><span>Raised by</span><strong>${escapeHtml(detail.raised_by || 'Unknown')}</strong></div>
            <div class="detail-box"><span>Job status</span><strong>${escapeHtml(detail.job_status || '—')}</strong></div>
          </div>
        </div>

        <div class="drawer-section">
          <h4>Issue</h4>
          <p>${escapeHtml(detail.description || 'No description was provided.')}</p>
        </div>

        <div class="drawer-section">
          <h4>Resolution</h4>
          <p>${escapeHtml(detail.resolution || 'No resolution recorded yet.')}</p>
          <div class="inline-actions">
            <button type="button" class="secondary-button" data-action="set-dispute-status" data-id="${detail.id}" data-status="UNDER_REVIEW">Mark under review</button>
            <button type="button" class="secondary-button" data-action="set-dispute-status" data-id="${detail.id}" data-status="RESOLVED">Mark resolved</button>
          </div>
        </div>

        <form id="dispute-resolution-form" data-dispute-id="${detail.id}" class="drawer-section">
          <h4>Resolution log</h4>
          <div class="field">
            <label for="resolution-text">Resolution summary</label>
            <textarea id="resolution-text" name="resolution" required placeholder="Document the investigation outcome, evidence review, and cooperative decision."></textarea>
          </div>
          <div class="form-error"></div>
          <div class="inline-actions">
            <button type="submit" class="primary-button">Record resolution</button>
          </div>
        </form>
      </div>
    `);
  } catch (error) {
    toast(error.message);
  }
}

async function updateDisputeStatus(disputeId, status) {
  try {
    await api(`/admin/disputes/${disputeId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    await refreshData();
    toast(`Dispute status updated to ${status}.`);
    closeDrawer();
  } catch (error) {
    toast(error.message);
  }
}

async function resolveDispute(disputeId) {
  const resolution = window.prompt('Document the final cooperative resolution for this dispute.');
  if (!resolution || !resolution.trim()) return;
  try {
    await api(`/admin/disputes/${disputeId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ resolution: resolution.trim() }),
    });
    await refreshData();
    toast('Dispute resolved.');
    closeDrawer();
  } catch (error) {
    toast(error.message);
  }
}

async function openComplaintDrawer(complaintId) {
  const complaint = state.complaints.find((item) => item.id === complaintId);
  if (!complaint) return;

  try {
    const detail = await api(`/admin/complaints/${complaintId}`);
    openDrawer(`
      <div class="drawer-head">
        <div class="drawer-heading">
          <div class="eyebrow">Complaint review</div>
          <h2>${escapeHtml(detail.category || 'Complaint')}</h2>
        </div>
        <button type="button" class="close-button" data-action="close-drawer" aria-label="Close complaint review">×</button>
      </div>
      <div class="drawer-body">
        <div class="drawer-section">
          <div class="detail-grid">
            <div class="detail-box"><span>Reporter</span><strong>${escapeHtml(detail.reporter_role || 'Unknown')}</strong></div>
            <div class="detail-box"><span>Status</span><strong>${escapeHtml(detail.status)}</strong></div>
            <div class="detail-box"><span>Job</span><strong>${escapeHtml(detail.job_id || '—')}</strong></div>
            <div class="detail-box"><span>Created</span><strong>${dateLabel(detail.created_at)}</strong></div>
          </div>
        </div>

        <div class="drawer-section">
          <h4>Message</h4>
          <p>${escapeHtml(detail.message || 'No message was provided.')}</p>
        </div>

        <div class="drawer-section">
          <h4>Admin response</h4>
          <p>${escapeHtml(detail.resolution || 'No response recorded yet.')}</p>
          <div class="inline-actions">
            <button type="button" class="secondary-button" data-action="set-complaint-status" data-id="${detail.id}" data-status="UNDER_REVIEW">Set under review</button>
            <button type="button" class="secondary-button" data-action="set-complaint-status" data-id="${detail.id}" data-status="RESOLVED">Mark resolved</button>
          </div>
        </div>

        <form id="complaint-response-form" data-complaint-id="${detail.id}" class="drawer-section">
          <h4>Send a response</h4>
          <div class="field">
            <label for="response-text">Response</label>
            <textarea id="response-text" name="response" required placeholder="Provide the cooperative response to the person reporting the complaint."></textarea>
          </div>
          <div class="form-error"></div>
          <div class="inline-actions">
            <button type="submit" class="primary-button">Save response</button>
          </div>
        </form>
      </div>
    `);
  } catch (error) {
    toast(error.message);
  }
}

async function updateComplaintStatus(complaintId, status) {
  try {
    await api(`/admin/complaints/${complaintId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    await refreshData();
    toast(`Complaint status updated to ${status}.`);
    closeDrawer();
  } catch (error) {
    toast(error.message);
  }
}

async function respondToComplaint(complaintId) {
  const response = window.prompt('Reply to this complaint as the cooperative admin.');
  if (!response || !response.trim()) return;
  try {
    await api(`/admin/complaints/${complaintId}/response`, {
      method: 'POST',
      body: JSON.stringify({ response: response.trim() }),
    });
    await refreshData();
    toast('Complaint response saved.');
    closeDrawer();
  } catch (error) {
    toast(error.message);
  }
}

function init() {
  if (state.token) {
    refreshData();
  } else {
    renderLogin();
  }
}

init();
