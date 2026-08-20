(function () {
  const DEFAULT_BRIDGE_URL = 'http://127.0.0.1:33343/health';
  const TIMEOUT_MS = 2200;
  const PLAN_TIMEOUT_MS = 45000;
  let bridgeState = { status: 'unknown' };
  let probing = false;
  let planning = false;

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function ensureStyles() {
    if (document.getElementById('pocketport-bridge-styles')) return;
    const style = document.createElement('style');
    style.id = 'pocketport-bridge-styles';
    style.textContent = `
      .bridge-card{margin-top:14px;padding:13px 14px;border:1px solid #1e2b24;border-radius:9px;background:#0b100d;display:flex;align-items:center;justify-content:space-between;gap:14px;font-size:12px;color:#9aa79f}
      .bridge-card strong{display:block;color:#d9e4dc;font-size:12px;font-weight:600;margin-bottom:3px}
      .bridge-card .bridge-meta{font-family:var(--mono);font-size:9px;color:#66736b;text-align:right;white-space:nowrap}
      .bridge-card .bridge-dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:7px;background:#72f59c;box-shadow:0 0 0 3px rgba(114,245,156,.11)}
      .bridge-connect{border:1px solid #2a3b31;background:#0d1510;color:#b8c6bd;border-radius:8px;padding:8px 10px;font-family:var(--mono);font-size:10px;white-space:nowrap}
      .bridge-connect:active{transform:translateY(1px)}
      .bridge-card.bridge-error .bridge-dot{background:#d8b46f;box-shadow:none}
      .local-plan-status{padding:15px;border:1px solid #203128;border-radius:9px;background:#0a100c;color:#9eaba3;font-size:13px;line-height:1.55}
      .local-plan-status strong{display:block;color:#e0e8e2;margin-bottom:5px}
      .local-plan-meta{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}
      .local-plan-meta span{border:1px solid #233129;border-radius:999px;padding:5px 8px;font-family:var(--mono);font-size:9px;color:#9baa9f}
      @media(max-width:430px){.bridge-card{align-items:flex-start}.bridge-card .bridge-meta{white-space:normal}.bridge-connect{margin-top:1px}}
    `;
    document.head.appendChild(style);
  }

  function bridgeHealthUrl() {
    const config = window.__POCKETPORT_CONFIG__ || {};
    return config.bridgeUrl || DEFAULT_BRIDGE_URL;
  }

  function bridgeEndpoint(path) {
    const health = bridgeHealthUrl();
    const base = health.replace(/\/(?:api\/)?health\/?$/, '');
    return `${base}${path}`;
  }

  async function queryLoopbackPermission() {
    if (!navigator.permissions || !navigator.permissions.query) return 'unknown';
    for (const name of ['loopback-network', 'local-network-access']) {
      try {
        const result = await navigator.permissions.query({ name });
        return result.state;
      } catch (_) {}
    }
    return 'unknown';
  }

  async function detectLocalBridge() {
    const url = bridgeHealthUrl();
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

    try {
      const response = await fetch(url, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
      });
      if (!response.ok) return { detected: false, reason: `HTTP ${response.status}` };
      const payload = await response.json();
      if (!payload || payload.ok !== true || payload.service !== 'pocketport-local-bridge') {
        return { detected: false, reason: 'unexpected response' };
      }
      return { detected: true, url, payload };
    } catch (error) {
      return {
        detected: false,
        reason: error && error.name === 'AbortError' ? 'timeout' : 'unreachable',
      };
    } finally {
      clearTimeout(timer);
    }
  }

  function canPlanLocally() {
    const payload = bridgeState.payload || {};
    return bridgeState.status === 'connected'
      && Number(payload.api || 0) >= 2
      && Array.isArray(payload.capabilities)
      && payload.capabilities.includes('local-plan');
  }

  function renderBridgeCard() {
    ensureStyles();
    const resultView = document.querySelector('.result-view');
    if (!resultView) return;
    const target = resultView.querySelector('.target-context');
    if (!target) return;

    let card = resultView.querySelector('[data-bridge-card]');
    if (!card) {
      card = document.createElement('div');
      card.dataset.bridgeCard = '1';
      target.insertAdjacentElement('afterend', card);
    }

    if (bridgeState.status === 'connected') {
      const payload = bridgeState.payload || {};
      const arch = payload.arch || 'unknown';
      const version = payload.version || 'unknown';
      const detail = canPlanLocally()
        ? 'Local Termux bridge is ready to build execution plans.'
        : 'Local Termux bridge is reachable.';
      card.className = 'bridge-card';
      card.innerHTML = `<div><strong><span class="bridge-dot"></span>PocketPort detected on this phone</strong><span>${detail}</span></div><div class="bridge-meta">${arch} · v${version}</div>`;
      const targetLabel = target.querySelector('span:first-child');
      const targetValue = target.querySelector('span:last-child');
      if (targetLabel) targetLabel.innerHTML = '<span class="target-dot"></span> Detected target';
      if (targetValue) targetValue.textContent = `Android / ${arch} / Termux yes`;
      return;
    }

    if (bridgeState.status === 'failed') {
      card.className = 'bridge-card bridge-error';
      card.innerHTML = `<div><strong><span class="bridge-dot"></span>Phone bridge not reachable</strong><span>Start <code>pocketport serve</code> in Termux, then retry.</span></div><button class="bridge-connect" type="button" data-bridge-connect>Retry</button>`;
      return;
    }

    card.className = 'bridge-card';
    card.innerHTML = `<div><strong>Connect this phone</strong><span>Allow PocketPort to check the local Termux bridge.</span></div><button class="bridge-connect" type="button" data-bridge-connect>Connect</button>`;
  }

  async function connect() {
    if (probing) return;
    probing = true;
    const button = document.querySelector('[data-bridge-connect]');
    if (button) button.textContent = 'Checking…';
    const result = await detectLocalBridge();
    bridgeState = result.detected
      ? { status: 'connected', payload: result.payload, url: result.url }
      : { status: 'failed', reason: result.reason };
    probing = false;
    renderBridgeCard();
  }

  async function maybeOfferBridge() {
    if (!document.querySelector('.result-view')) return;
    if (bridgeState.status === 'connected' || bridgeState.status === 'failed') {
      renderBridgeCard();
      return;
    }

    const permission = await queryLoopbackPermission();
    if (permission === 'granted') {
      await connect();
      return;
    }
    renderBridgeCard();
  }

  function repoUrlFromRoute() {
    const match = location.pathname.replace(/\/+$/, '').match(/^\/scan\/([^/]+)\/([^/]+)$/);
    if (!match) return null;
    try {
      const owner = decodeURIComponent(match[1]);
      const repo = decodeURIComponent(match[2]);
      return `https://github.com/${owner}/${repo}`;
    } catch (_) {
      return null;
    }
  }

  function openLocalSheet(kicker, title, html) {
    const sheet = document.getElementById('sheet');
    const backdrop = document.getElementById('sheet-backdrop');
    const sheetKicker = document.getElementById('sheet-kicker');
    const sheetTitle = document.getElementById('sheet-title');
    const sheetBody = document.getElementById('sheet-body');
    if (!sheet || !backdrop || !sheetKicker || !sheetTitle || !sheetBody) return;

    sheetKicker.textContent = kicker;
    sheetTitle.textContent = title;
    sheetBody.innerHTML = html;
    sheet.hidden = false;
    backdrop.hidden = false;
    requestAnimationFrame(() => document.body.classList.add('sheet-open'));
  }

  async function planRepository(repository) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), PLAN_TIMEOUT_MS);
    try {
      const response = await fetch(bridgeEndpoint('/api/plan'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repository }),
        cache: 'no-store',
        signal: controller.signal,
      });
      let payload = null;
      try { payload = await response.json(); } catch (_) {}
      if (!response.ok) {
        const message = payload?.error || `Local PocketPort returned HTTP ${response.status}`;
        throw new Error(message);
      }
      if (!payload?.execution_plan) throw new Error('Local PocketPort returned no execution plan.');
      return payload;
    } catch (error) {
      if (error && error.name === 'AbortError') throw new Error('Local planning timed out.');
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  function renderPlanPayload(payload) {
    const plan = payload.execution_plan || {};
    const commands = [...(plan.install || []), ...(plan.run || [])];
    const commandHtml = commands.length
      ? commands.map(command => `<div class="command-block"><code>${escapeHtml(command)}</code><button type="button" class="copy-button" data-copy="${escapeHtml(command)}">Copy</button></div>`).join('')
      : '<div class="sheet-note">PocketPort found no safe process command for this artifact.</div>';
    const notes = (plan.notes || []).map(note => `<div class="sheet-note">${escapeHtml(note)}</div>`).join('');
    const device = payload.device || {};
    const meta = `<div class="local-plan-meta"><span>LOCAL DEVICE</span><span>${escapeHtml(device.arch || 'unknown')}</span><span>v${escapeHtml(device.version || 'unknown')}</span><span>${escapeHtml(payload.strategy || 'unknown')}</span></div>`;
    openLocalSheet(
      'LOCAL EXECUTION PLAN',
      `${plan.status || 'plan'} · ${plan.method || 'PocketPort'}`,
      `${meta}<p class="sheet-copy">Generated now by PocketPort Core running in this phone's Termux. The browser did not invent these commands.</p>${commandHtml}${notes}`,
    );
  }

  async function usePocketPortLocally() {
    if (planning) return;
    const repository = repoUrlFromRoute();
    if (!repository) return;
    planning = true;
    openLocalSheet(
      'LOCAL DEVICE',
      'Building execution plan…',
      '<div class="local-plan-status"><strong>PocketPort is scanning this repository on your phone.</strong>GitHub archive → semantic scan → execution plan. Nothing is installed or executed yet.</div>',
    );
    try {
      const payload = await planRepository(repository);
      renderPlanPayload(payload);
    } catch (error) {
      openLocalSheet(
        'LOCAL DEVICE',
        'Local planning failed',
        `<div class="local-plan-status"><strong>PocketPort could not build the local plan.</strong>${escapeHtml(error?.message || 'Unknown local bridge error.')}</div>`,
      );
    } finally {
      planning = false;
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-bridge-connect]');
    if (!button) return;
    connect();
  });

  document.addEventListener('click', event => {
    const button = event.target.closest('#use-pocketport');
    if (!button || !canPlanLocally()) return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    usePocketPortLocally();
  }, true);

  const observer = new MutationObserver(() => { maybeOfferBridge(); });
  const app = document.getElementById('app');
  if (app) observer.observe(app, { childList: true });
  maybeOfferBridge();

  window.PocketPortBridge = {
    detectLocalBridge,
    connect,
    planRepository,
    canPlanLocally,
  };
})();
