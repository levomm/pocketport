(function () {
  const DEFAULT_BRIDGE_URL = 'http://127.0.0.1:8765/health';
  const TIMEOUT_MS = 2200;
  let bridgeState = { status: 'unknown' };
  let probing = false;

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
      @media(max-width:430px){.bridge-card{align-items:flex-start}.bridge-card .bridge-meta{white-space:normal}.bridge-connect{margin-top:1px}}
    `;
    document.head.appendChild(style);
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
    const config = window.__POCKETPORT_CONFIG__ || {};
    const url = config.bridgeUrl || DEFAULT_BRIDGE_URL;
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
      card.className = 'bridge-card';
      card.innerHTML = `<div><strong><span class="bridge-dot"></span>PocketPort detected on this phone</strong><span>Local Termux bridge is reachable.</span></div><div class="bridge-meta">${arch} · v${version}</div>`;
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

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-bridge-connect]');
    if (!button) return;
    connect();
  });

  const observer = new MutationObserver(() => { maybeOfferBridge(); });
  const app = document.getElementById('app');
  if (app) observer.observe(app, { childList: true, subtree: true });
  maybeOfferBridge();

  window.PocketPortBridge = { detectLocalBridge, connect };
})();
