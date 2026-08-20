(function () {
  const app = document.getElementById('app');
  const sheet = document.getElementById('sheet');
  const sheetBackdrop = document.getElementById('sheet-backdrop');
  const sheetClose = document.getElementById('sheet-close');
  const sheetTitle = document.getElementById('sheet-title');
  const sheetKicker = document.getElementById('sheet-kicker');
  const sheetBody = document.getElementById('sheet-body');
  const targetPillText = document.getElementById('target-pill-text');
  let activeController = null;
  const cache = new Map();

  const DEFAULT_TARGET = { platform: 'Android', arch: 'arm64', termux: 'yes', proot: 'unknown' };
  const SCOPE_ORDER = ['runtime', 'build', 'optional', 'dev', 'ci', 'metadata'];
  const SCOPE_LABEL = { runtime: 'Runtime', build: 'Build', optional: 'Optional', dev: 'Dev', ci: 'CI', metadata: 'Metadata' };

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function getTarget() {
    try { return { ...DEFAULT_TARGET, ...(JSON.parse(localStorage.getItem('pocketport-target')) || {}) }; }
    catch { return { ...DEFAULT_TARGET }; }
  }

  function setTarget(next) {
    localStorage.setItem('pocketport-target', JSON.stringify(next));
    updateTargetPill();
  }

  function updateTargetPill() {
    const target = getTarget();
    targetPillText.textContent = `${target.platform} · ${target.arch}`;
  }

  function getRecents() {
    try { return JSON.parse(localStorage.getItem('pocketport-recents')) || []; }
    catch { return []; }
  }

  function rememberScan(envelope, verdict) {
    if (envelope.source === 'unavailable') return;
    const next = [
      { slug: envelope.repo.displaySlug, url: envelope.repo.url, verdict: verdict.label, source: envelope.source, at: Date.now() },
      ...getRecents().filter(item => item.slug.toLowerCase() !== envelope.repo.slug),
    ].slice(0, 6);
    localStorage.setItem('pocketport-recents', JSON.stringify(next));
  }

  function verdictFor(report) {
    const artifact = report.artifact || {};
    const type = artifact.type || 'application';
    const runtime = (report.findings || []).filter(f => (f.scope || 'runtime') === 'runtime');
    const runtimeHigh = runtime.some(f => f.severity === 'high');
    const runtimeMeaningful = runtime.some(f => ['high', 'medium'].includes(f.severity));

    if (type === 'agent-skill') {
      return { key: 'native', label: 'Agent skill', summary: 'This repository is installed into a compatible agent such as Codex or Claude Code; it is not a standalone process to run.' };
    }
    if (type === 'library') {
      return { key: 'native', label: 'Library / package', summary: 'PocketPort found an installable package, not a standalone application. Use it as a dependency rather than looking for a Run command.' };
    }
    if (type === 'desktop-app') {
      return { key: 'fallback', label: 'Desktop app', summary: 'This is a graphical desktop target. PRoot alone does not make the GUI a normal stock-Termux application.' };
    }
    if (report.strategy === 'proot') {
      return { key: 'fallback', label: 'Needs Linux fallback', summary: 'PocketPort sees Linux assumptions that are better handled through a fallback environment.' };
    }
    if (report.strategy === 'hybrid' || runtimeHigh) {
      return { key: 'partial', label: 'Partially compatible', summary: 'Useful parts can run on Android, but the primary runtime still needs adaptation or OS capabilities.' };
    }
    if (report.strategy === 'native' && runtimeMeaningful) {
      return { key: 'fixes', label: 'Needs PocketPort fixes', summary: 'The primary runtime has a direct Android path, with meaningful assumptions PocketPort still needs to handle.' };
    }
    return { key: 'native', label: 'Runs natively', summary: 'PocketPort found a direct Android and Termux path without meaningful runtime blockers.' };
  }

  function navigate(path, replace = false) {
    if (replace) history.replaceState({}, '', path); else history.pushState({}, '', path);
    renderRoute();
  }

  function parseRoute() {
    const path = location.pathname.replace(/\/+$/, '') || '/';
    if (path === '/') return { name: 'home' };
    if (path === '/target') return { name: 'target' };
    const match = path.match(/^\/scan\/([^/]+)\/([^/]+)$/);
    if (match) return { name: 'scan', owner: decodeURIComponent(match[1]), repo: decodeURIComponent(match[2]) };
    return { name: 'home' };
  }

  function renderRoute() {
    closeSheet();
    if (activeController) activeController.abort();
    const route = parseRoute();
    if (route.name === 'target') return renderTarget();
    if (route.name === 'scan') return renderScan(route.owner, route.repo);
    renderHome();
  }

  function renderHome() {
    document.title = 'PocketPort · GitHub projects on Android';
    const recents = getRecents();
    app.innerHTML = `
      <section class="home-view view">
        <div class="hero-block">
          <p class="eyebrow">ANDROID / TERMUX COMPATIBILITY</p>
          <h1>Can this GitHub project run on <span>your phone?</span></h1>
          <p class="hero-copy">Paste a repository. PocketPort reads the project, finds the Android path, and tells you what will actually run.</p>
        </div>

        <form id="scan-form" class="scan-form" novalidate>
          <label class="field-label" for="repo-input">GitHub repository</label>
          <div class="repo-input-wrap">
            <span class="repo-prefix">github.com/</span>
            <textarea id="repo-input" rows="2" spellcheck="false" autocomplete="off" placeholder="owner/repository" aria-describedby="repo-error"></textarea>
          </div>
          <p id="repo-error" class="field-error" role="alert"></p>
          <button class="primary-button" type="submit"><span>Scan repository</span><span class="button-arrow">↗</span></button>
        </form>

        <div class="home-footnote">
          <span class="pulse-dot"></span><span>Target</span>
          <button type="button" data-nav="/target" class="inline-link">${escapeHtml(getTarget().platform)} · ${escapeHtml(getTarget().arch)}</button>
        </div>

        ${recents.length ? `
          <section class="recent-section">
            <div class="section-head"><p class="eyebrow">RECENT SCANS</p><span>${recents.length}</span></div>
            <div class="recent-list">
              ${recents.map(item => `
                <button class="recent-row" type="button" data-repo-url="${escapeHtml(item.url)}">
                  <span class="mono">${escapeHtml(item.slug)}</span><span class="recent-verdict">${escapeHtml(item.verdict)}</span><span class="row-arrow">›</span>
                </button>`).join('')}
            </div>
          </section>` : ''}
      </section>`;

    const form = document.getElementById('scan-form');
    const input = document.getElementById('repo-input');
    const error = document.getElementById('repo-error');
    form.addEventListener('submit', event => {
      event.preventDefault();
      const ref = PocketPortAdapter.normalizeRepo(input.value);
      if (!ref) {
        error.textContent = 'Paste a GitHub repository URL or owner/repository.';
        input.classList.add('invalid');
        return;
      }
      navigate(`/scan/${encodeURIComponent(ref.owner)}/${encodeURIComponent(ref.repo)}`);
    });
    input.addEventListener('input', () => { input.classList.remove('invalid'); error.textContent = ''; });
    input.addEventListener('paste', () => setTimeout(() => {
      const ref = PocketPortAdapter.normalizeRepo(input.value);
      if (ref) input.value = ref.displaySlug;
    }, 0));
  }

  function renderLoading(repoRef) {
    app.innerHTML = `
      <section class="scan-state view">
        <button type="button" class="back-link" data-nav="/">← New scan</button>
        <div class="scan-state-center">
          <p class="mono repo-slug">${escapeHtml(repoRef.displaySlug)}</p>
          <div class="scan-orbit" aria-hidden="true"><span></span></div>
          <h1>Scanning repository…</h1>
          <p>PocketPort is analyzing compatibility.</p>
          <button id="cancel-scan" class="quiet-button" type="button">Cancel</button>
        </div>
      </section>`;
    document.getElementById('cancel-scan').addEventListener('click', () => {
      if (activeController) activeController.abort();
      navigate('/');
    });
  }

  async function renderScan(owner, repo) {
    const ref = PocketPortAdapter.normalizeRepo(`${owner}/${repo}`);
    if (!ref) return navigate('/', true);
    document.title = `${ref.displaySlug} · PocketPort`;
    renderLoading(ref);
    activeController = new AbortController();
    try {
      let envelope = cache.get(ref.slug);
      if (!envelope) {
        envelope = await PocketPortAdapter.scanRepository(ref, activeController.signal);
        cache.set(ref.slug, envelope);
      }
      if (envelope.source === 'unavailable') renderUnavailable(envelope);
      else renderResult(envelope);
    } catch (error) {
      if (error && error.name === 'AbortError') return;
      renderUnavailable({ source: 'unavailable', repo: ref, reason: error?.message || 'PocketPort scanner could not be reached.' });
    } finally {
      activeController = null;
    }
  }

  function renderUnavailable(envelope) {
    app.innerHTML = `
      <section class="result-view view">
        <button type="button" class="back-link" data-nav="/">← New scan</button>
        <div class="unavailable-block">
          <p class="mono repo-slug">${escapeHtml(envelope.repo.displaySlug)}</p>
          <p class="eyebrow">SCANNER UNAVAILABLE</p><h1>No verdict yet.</h1><p>${escapeHtml(envelope.reason)}</p>
          <div class="unavailable-note">This interface refuses to invent a compatibility score. Connect the PocketPort scan service or use PocketPort in Termux.</div>
          <button class="primary-button" id="unavailable-use" type="button">Use with PocketPort <span class="button-arrow">↗</span></button>
        </div>
      </section>`;
    document.getElementById('unavailable-use').addEventListener('click', () => openUseSheet(envelope.repo));
  }

  function renderResult(envelope) {
    const { report, repo } = envelope;
    const verdict = verdictFor(report);
    rememberScan(envelope, verdict);
    const target = getTarget();
    const components = report.components || [];
    const artifactType = report.artifact?.type || 'application';
    const grouped = SCOPE_ORDER.map(scope => [scope, (report.findings || []).filter(f => (f.scope || 'runtime') === scope)]).filter(([, items]) => items.length);

    app.innerHTML = `
      <section class="result-view view verdict-${verdict.key}">
        <button type="button" class="back-link" data-nav="/">← New scan</button>
        <header class="result-hero">
          <div class="repo-line"><span class="mono repo-slug">${escapeHtml(repo.displaySlug)}</span><span class="provenance">${envelope.source === 'service' ? 'Live scan' : 'Recorded scan'}</span></div>
          <p class="eyebrow">POCKETPORT VERDICT · ${escapeHtml(artifactType.toUpperCase())}</p>
          <h1>${escapeHtml(verdict.label)}</h1>
          <p class="result-summary">${escapeHtml(verdict.summary)}</p>
        </header>

        <div class="metric-rail">
          <div><span class="metric-label">Score</span><strong class="mono">${escapeHtml(report.score)}/100</strong></div>
          <div><span class="metric-label">Strategy</span><strong class="mono">${escapeHtml(report.strategy)}</strong></div>
          <div class="metric-stack"><span class="metric-label">Stack</span><strong class="mono">${escapeHtml((report.stack || []).join(' · '))}</strong></div>
        </div>

        <button type="button" class="target-context" data-nav="/target">
          <span><span class="target-dot"></span> Assumed target</span>
          <span class="mono">${escapeHtml(target.platform)} / ${escapeHtml(target.arch)} / Termux ${escapeHtml(target.termux)}</span>
        </button>

        ${report.artifact?.requirements?.length ? `
          <section class="content-section">
            <div class="section-title-row"><div><p class="eyebrow">REQUIREMENTS</p><h2>What it actually needs</h2></div><span class="section-count mono">${report.artifact.requirements.length}</span></div>
            <div class="finding-list">${report.artifact.requirements.map(item => `<article class="finding-item"><p>${escapeHtml(item)}</p></article>`).join('')}</div>
          </section>` : ''}

        ${components.length ? `
          <section class="content-section">
            <div class="section-title-row"><div><p class="eyebrow">COMPONENTS</p><h2>Runnable surfaces</h2></div><span class="section-count mono">${components.length}</span></div>
            <div class="component-list">
              ${components.map((component, index) => `
                <details class="component-row" ${index === 0 ? 'open' : ''}>
                  <summary>
                    <div class="component-main"><strong>${escapeHtml(component.name)}</strong><span>${escapeHtml(component.role)}</span></div>
                    <div class="component-score mono">${escapeHtml(component.score)}/100</div><div class="strategy-tag mono">${escapeHtml(component.strategy)}</div><span class="disclosure">+</span>
                  </summary>
                  <div class="component-detail"><div><span>Path</span><code>${escapeHtml(component.path)}</code></div><div><span>Stack</span><code>${escapeHtml((component.stack || []).join(' · '))}</code></div></div>
                </details>`).join('')}
            </div>
          </section>` : ''}

        <section class="content-section">
          <div class="section-title-row"><div><p class="eyebrow">COMPATIBILITY FINDINGS</p><h2>What PocketPort noticed</h2></div><span class="section-count mono">${(report.findings || []).length}</span></div>
          <div class="finding-groups">
            ${grouped.map(([scope, findings]) => `
              <details class="finding-group">
                <summary><div><strong>${SCOPE_LABEL[scope]}</strong><span>${scope === 'runtime' ? 'Affects actual execution' : 'Visible but lower impact'}</span></div><div class="group-count mono">${findings.length}</div><span class="disclosure">+</span></summary>
                <div class="finding-list">
                  ${findings.map(f => `<article class="finding-item severity-${escapeHtml(f.severity)}"><div class="finding-meta"><span class="severity-dot"></span><span class="mono">${escapeHtml(f.severity)}</span><span class="mono kind">${escapeHtml(f.kind)}</span></div><p>${escapeHtml(f.detail)}</p>${f.path ? `<code>${escapeHtml(f.path)}</code>` : ''}</article>`).join('')}
                </div>
              </details>`).join('')}
          </div>
        </section>

        <section class="technical-links"><button type="button" id="raw-json">Raw scanner JSON</button><span>·</span><button type="button" data-nav="/target">Target settings</button></section>
        <div class="sticky-action-space"></div>
        <div class="sticky-action"><button id="use-pocketport" class="primary-button" type="button"><span>Use with PocketPort</span><span class="button-arrow">↗</span></button></div>
      </section>`;

    document.getElementById('use-pocketport').addEventListener('click', () => openUseSheet(repo, report));
    document.getElementById('raw-json').addEventListener('click', () => openRawSheet(report));
  }

  function renderTarget() {
    document.title = 'Target device · PocketPort';
    const target = getTarget();
    app.innerHTML = `
      <section class="target-view view">
        <button type="button" class="back-link" onclick="history.length > 1 ? history.back() : location.assign('/')">← Back</button>
        <div class="target-header"><p class="eyebrow">TARGET DEVICE</p><h1>Tell PocketPort what phone you mean.</h1><p>The browser cannot reliably inspect Termux or PRoot. These are declared assumptions until PocketPort runs directly on-device.</p></div>
        <form id="target-form" class="target-form">
          <div class="setting-row locked"><div><label>Platform</label><p>Mobile operating system</p></div><strong class="mono">Android</strong></div>
          <fieldset class="setting-block"><legend>Architecture</legend><div class="segmented">${['arm64','arm','x86_64'].map(v => `<label><input type="radio" name="arch" value="${v}" ${target.arch === v ? 'checked' : ''}><span class="mono">${v}</span></label>`).join('')}</div></fieldset>
          <fieldset class="setting-block"><legend>Termux</legend><div class="segmented two">${['yes','no'].map(v => `<label><input type="radio" name="termux" value="${v}" ${target.termux === v ? 'checked' : ''}><span>${v === 'yes' ? 'Installed' : 'Not installed'}</span></label>`).join('')}</div></fieldset>
          <fieldset class="setting-block"><legend>PRoot</legend><div class="segmented three">${['available','unavailable','unknown'].map(v => `<label><input type="radio" name="proot" value="${v}" ${target.proot === v ? 'checked' : ''}><span>${v}</span></label>`).join('')}</div></fieldset>
          <div class="target-note"><span>i</span><p>These settings do not change PocketPort's scanner score. They describe the device the result is being interpreted for.</p></div>
          <button class="primary-button" type="submit">Save target <span class="button-arrow">↗</span></button>
        </form>
      </section>`;

    document.getElementById('target-form').addEventListener('submit', event => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      setTarget({ platform: 'Android', arch: data.get('arch'), termux: data.get('termux'), proot: data.get('proot') });
      history.length > 1 ? history.back() : navigate('/');
    });
  }

  function openSheet(kicker, title, html) {
    sheetKicker.textContent = kicker;
    sheetTitle.textContent = title;
    sheetBody.innerHTML = html;
    sheetBackdrop.hidden = false;
    sheet.hidden = false;
    requestAnimationFrame(() => document.body.classList.add('sheet-open'));
  }

  function closeSheet() {
    document.body.classList.remove('sheet-open');
    if (!sheet.hidden) setTimeout(() => { sheet.hidden = true; sheetBackdrop.hidden = true; }, 180);
  }

  function openUseSheet(repo, report = null) {
    const plan = report?.execution_plan;
    if (!plan) {
      const command = `pocketport scan ${repo.url}`;
      openSheet('TERMUX', 'Use with PocketPort', `<p class="sheet-copy">Continue in Termux with the command PocketPort supports:</p><div class="command-block"><code>${escapeHtml(command)}</code><button type="button" class="copy-button" data-copy="${escapeHtml(command)}">Copy</button></div>`);
      return;
    }

    const commands = [...(plan.install || []), ...(plan.run || [])];
    const commandHtml = commands.length
      ? commands.map(command => `<div class="command-block"><code>${escapeHtml(command)}</code><button type="button" class="copy-button" data-copy="${escapeHtml(command)}">Copy</button></div>`).join('')
      : '<div class="sheet-note">PocketPort has no safe process command for this artifact type.</div>';
    const notes = (plan.notes || []).map(note => `<div class="sheet-note">${escapeHtml(note)}</div>`).join('');
    openSheet('EXECUTION PLAN', `${escapeHtml(plan.status)} · ${escapeHtml(plan.method)}`, `<p class="sheet-copy">PocketPort Core produced this plan from repository metadata. The web UI is only displaying it.</p>${commandHtml}${notes}`);
  }

  function openRawSheet(report) {
    openSheet('TECHNICAL DETAILS', 'Raw scanner JSON', `<pre class="raw-json">${escapeHtml(JSON.stringify(report, null, 2))}</pre>`);
  }

  document.addEventListener('click', event => {
    const nav = event.target.closest('[data-nav]');
    if (nav) { event.preventDefault(); navigate(nav.dataset.nav); return; }
    const recent = event.target.closest('[data-repo-url]');
    if (recent) {
      const ref = PocketPortAdapter.normalizeRepo(recent.dataset.repoUrl);
      if (ref) navigate(`/scan/${encodeURIComponent(ref.owner)}/${encodeURIComponent(ref.repo)}`);
      return;
    }
    const copy = event.target.closest('[data-copy]');
    if (copy) {
      navigator.clipboard?.writeText(copy.dataset.copy);
      const old = copy.textContent;
      copy.textContent = 'Copied';
      setTimeout(() => copy.textContent = old, 1200);
    }
  });

  sheetClose.addEventListener('click', closeSheet);
  sheetBackdrop.addEventListener('click', closeSheet);
  window.addEventListener('popstate', renderRoute);
  updateTargetPill();
  renderRoute();
})();