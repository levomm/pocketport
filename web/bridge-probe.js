(function () {
  const DEFAULT_BRIDGE_URL = 'http://127.0.0.1:8765/health';
  const TIMEOUT_MS = 1800;

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

  window.PocketPortBridge = { detectLocalBridge };
})();
