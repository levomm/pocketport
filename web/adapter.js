(function () {
  const recorded = {
    'deepseek-ai/deepseek-harness': '/recorded-scans/deepseek-harness.json',
    'plandex-ai/plandex': '/recorded-scans/plandex.json',
  };

  function normalizeRepo(input) {
    const raw = String(input || '').trim().replace(/\.git\/?$/, '').replace(/\/$/, '');
    const match = raw.match(/^(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/]+)$/i) || raw.match(/^([^/]+)\/([^/]+)$/);
    if (!match) return null;
    const owner = match[1];
    const repo = match[2];
    if (!owner || !repo) return null;
    return {
      owner,
      repo,
      slug: `${owner}/${repo}`.toLowerCase(),
      displaySlug: `${owner}/${repo}`,
      url: `https://github.com/${owner}/${repo}`,
    };
  }

  async function scanRepository(repoRef, signal) {
    const config = window.__POCKETPORT_CONFIG__ || {};
    const scanUrl = config.scanUrl === false ? null : (config.scanUrl || '/api/scan');
    let serviceReason = 'PocketPort scanner service could not be reached.';

    if (scanUrl) {
      try {
        const response = await fetch(scanUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ repository: repoRef.url }),
          signal,
        });
        if (response.ok) {
          const report = await response.json();
          return { source: 'service', repo: repoRef, report };
        }

        const errorPayload = await response.json().catch(() => null);
        if (errorPayload && errorPayload.error) serviceReason = errorPayload.error;
        else serviceReason = `PocketPort scanner returned HTTP ${response.status}.`;
      } catch (error) {
        if (error && error.name === 'AbortError') throw error;
      }
    }

    const fixture = recorded[repoRef.slug];
    if (fixture) {
      const response = await fetch(fixture, { signal });
      if (!response.ok) throw new Error('Recorded PocketPort scan could not be loaded.');
      const report = await response.json();
      return { source: 'recorded', repo: repoRef, report };
    }

    return {
      source: 'unavailable',
      repo: repoRef,
      reason: serviceReason,
    };
  }

  window.PocketPortAdapter = { normalizeRepo, scanRepository };
})();
