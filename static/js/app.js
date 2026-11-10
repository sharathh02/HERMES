/**
 * HERMES AI Documentation Intelligence Platform
 * Frontend Application Controller
 */

const state = {
  activeView: 'public', // 'public' | 'workspace'
  activeTab: 'overview', // 'overview' | 'docs' | 'analysis' | 'assistant' | 'tests' | 'github' | 'activity' | 'settings'
  stats: {},
  documents: [],
  selectedDoc: null,
  sampleFiles: [],
  selectedSample: null,
  currentSourceCode: '',
  currentAst: null,
  verificationRuns: [],
  pullRequests: [],
  activities: [],
  settings: {},
  theme: localStorage.getItem('hermes_theme') || 'light'
};

// Initialize application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  applyTheme(state.theme);
  bindEvents();
  loadInitialData();
});

function applyTheme(theme) {
  state.theme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('hermes_theme', theme);
  const themeBtn = document.getElementById('theme-toggle-btn');
  if (themeBtn) {
    themeBtn.textContent = theme === 'dark' ? '☀️ Light' : '🌙 Dark';
  }
}

function bindEvents() {
  // Theme toggle
  const themeBtn = document.getElementById('theme-toggle-btn');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      applyTheme(state.theme === 'dark' ? 'light' : 'dark');
    });
  }

  // View navigation: Public <-> Workspace
  document.querySelectorAll('[data-view-target]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const target = el.getAttribute('data-view-target');
      switchView(target);
    });
  });

  // Sidebar navigation
  document.querySelectorAll('[data-tab]').forEach(el => {
    el.addEventListener('click', (e) => {
      e.preventDefault();
      const tab = el.getAttribute('data-tab');
      switchTab(tab);
    });
  });

  // Global search input
  const searchInput = document.getElementById('global-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      handleGlobalSearch(e.target.value);
    });
  }

  // Document catalog search
  const docSearchInput = document.getElementById('doc-search-input');
  if (docSearchInput) {
    docSearchInput.addEventListener('input', (e) => {
      renderDocCatalog(e.target.value);
    });
  }

  // Assistant prompt submission
  const assistantForm = document.getElementById('assistant-form');
  if (assistantForm) {
    assistantForm.addEventListener('submit', (e) => {
      e.preventDefault();
      submitAssistantQuery();
    });
  }

  // Assistant suggestion chips
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.getAttribute('data-query');
      const input = document.getElementById('assistant-input');
      if (input) {
        input.value = query;
        submitAssistantQuery();
      }
    });
  });

  // Settings form submission
  const settingsForm = document.getElementById('settings-form');
  if (settingsForm) {
    settingsForm.addEventListener('submit', (e) => {
      e.preventDefault();
      saveSettings();
    });
  }
}

async function loadInitialData() {
  await Promise.all([
    fetchStats(),
    fetchDocuments(),
    fetchSamples(),
    fetchRuns(),
    fetchPullRequests(),
    fetchActivities(),
    fetchSettings()
  ]);
  renderOverview();
}

function switchView(viewName) {
  state.activeView = viewName;
  const publicView = document.getElementById('public-view');
  const workspaceView = document.getElementById('workspace-view');

  if (viewName === 'workspace') {
    publicView.style.display = 'none';
    workspaceView.style.display = 'flex';
    refreshCurrentTabData();
  } else {
    publicView.style.display = 'block';
    workspaceView.style.display = 'none';
  }
}

function switchTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll('[data-tab]').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-tab') === tabName);
  });
  document.querySelectorAll('.workspace-panel').forEach(panel => {
    panel.style.display = panel.id === `panel-${tabName}` ? 'block' : 'none';
  });
  refreshCurrentTabData();
}

function refreshCurrentTabData() {
  switch (state.activeTab) {
    case 'overview':
      fetchStats().then(renderOverview);
      break;
    case 'docs':
      fetchDocuments().then(() => renderDocCatalog());
      break;
    case 'analysis':
      renderCodeAnalysis();
      break;
    case 'tests':
      fetchRuns().then(renderVerificationRuns);
      break;
    case 'github':
      fetchPullRequests().then(renderPullRequests);
      break;
    case 'activity':
      fetchActivities().then(renderActivities);
      break;
    case 'settings':
      renderSettings();
      break;
  }
}

// ==========================================
// API Fetchers
// ==========================================

async function fetchStats() {
  try {
    const res = await fetch('/api/stats');
    state.stats = await res.json();
    updateBadgeCounts();
  } catch (err) {
    console.error('Failed to fetch stats:', err);
  }
}

async function fetchDocuments() {
  try {
    const res = await fetch('/api/documents');
    state.documents = await res.json();
    if (!state.selectedDoc && state.documents.length > 0) {
      await loadDocumentDetail(state.documents[0].id);
    }
  } catch (err) {
    console.error('Failed to fetch documents:', err);
  }
}

async function loadDocumentDetail(docId) {
  try {
    const res = await fetch(`/api/documents/${docId}`);
    state.selectedDoc = await res.json();
    renderDocViewer();
  } catch (err) {
    console.error('Failed to load document detail:', err);
  }
}

async function fetchSamples() {
  try {
    const res = await fetch('/api/samples');
    state.sampleFiles = await res.json();
    if (state.sampleFiles.length > 0 && !state.selectedSample) {
      selectSampleFile(state.sampleFiles[0].filename);
    }
  } catch (err) {
    console.error('Failed to fetch samples:', err);
  }
}

async function fetchRuns() {
  try {
    const res = await fetch('/api/runs');
    state.verificationRuns = await res.json();
  } catch (err) {
    console.error('Failed to fetch runs:', err);
  }
}

async function fetchPullRequests() {
  try {
    const res = await fetch('/api/pull-requests');
    state.pullRequests = await res.json();
  } catch (err) {
    console.error('Failed to fetch pull requests:', err);
  }
}

async function fetchActivities() {
  try {
    const res = await fetch('/api/activities');
    state.activities = await res.json();
  } catch (err) {
    console.error('Failed to fetch activities:', err);
  }
}

async function fetchSettings() {
  try {
    const res = await fetch('/api/settings');
    state.settings = await res.json();
  } catch (err) {
    console.error('Failed to fetch settings:', err);
  }
}

function updateBadgeCounts() {
  const docsCount = document.getElementById('count-docs');
  if (docsCount) docsCount.textContent = state.stats.documents_count || '0';

  const testCount = document.getElementById('count-tests');
  if (testCount) testCount.textContent = state.stats.verification_total || '0';

  const prCount = document.getElementById('count-prs');
  if (prCount) prCount.textContent = state.stats.pull_requests_count || '0';
}

// ==========================================
// Panel Renderers
// ==========================================

async function runDocumentSnippetVerification() {
  if (!state.selectedDoc) {
    showToast('No document selected to verify');
    return;
  }
  showToast(`Verifying snippets for ${state.selectedDoc.title}...`);
  try {
    const res = await fetch('/api/verify', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        content: state.selectedDoc.content,
        document_id: state.selectedDoc.id
      })
    });
    const data = await res.json();
    if (data.all_passed) {
      showToast(`All ${data.results.length} snippet(s) passed execution verification!`);
    } else {
      showToast('Some snippets failed verification. Check Tests tab.');
    }
    await fetchRuns();
    await fetchStats();
  } catch (err) {
    console.error('Verification failed:', err);
    showToast('Snippet verification request failed');
  }
}

function renderOverview() {
  const s = state.stats;
  document.getElementById('metric-synced-docs').textContent = s.synced_count ?? '0';
  document.getElementById('metric-drift-detected').textContent = s.drift_count ?? '0';
  document.getElementById('metric-pass-rate').textContent = (s.verification_pass_rate ?? 0) + '%';
  document.getElementById('metric-corrections').textContent = s.correction_runs ?? '0';
  document.getElementById('metric-staged-prs').textContent = s.pull_requests_count ?? '0';

  // Render recent activity feed on overview
  const activityList = document.getElementById('overview-activity-list');
  if (activityList) {
    if (!state.activities || state.activities.length === 0) {
      activityList.innerHTML = `<div style="color: var(--text-faint); padding: 12px 0;">No activities recorded yet.</div>`;
      return;
    }
    activityList.innerHTML = state.activities.slice(0, 5).map(a => `
      <div style="display: flex; align-items: flex-start; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border-subtle);">
        <span class="badge ${a.severity === 'success' ? 'badge-pass' : a.severity === 'warning' ? 'badge-warn' : 'badge-neutral'}">
          ${escapeHtml(a.event_type)}
        </span>
        <div style="flex: 1;">
          <div style="font-weight: 600; font-size: 13px;">${escapeHtml(a.title)}</div>
          <div style="font-size: 12px; color: var(--text-muted);">${escapeHtml(a.description)}</div>
        </div>
        <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-faint);">
          ${formatTimestamp(a.created_at)}
        </div>
      </div>
    `).join('');
  }
}

function renderDocCatalog(filter = '') {
  const list = document.getElementById('doc-catalog-list');
  if (!list) return;

  const filtered = state.documents.filter(d => 
    d.title.toLowerCase().includes(filter.toLowerCase()) || 
    (d.file_path && d.file_path.toLowerCase().includes(filter.toLowerCase()))
  );

  if (filtered.length === 0) {
    list.innerHTML = `<li style="padding: 16px; color: var(--text-faint); text-align: center;">No documents match query.</li>`;
    return;
  }

  list.innerHTML = filtered.map(d => `
    <li class="catalog-item ${state.selectedDoc && state.selectedDoc.id === d.id ? 'active' : ''}" onclick="loadDocumentDetail(${d.id})">
      <div class="catalog-title">${escapeHtml(d.title)}</div>
      <div class="catalog-meta">
        <span class="badge ${d.status === 'synced' ? 'badge-pass' : 'badge-warn'}">${d.status}</span>
        <span>v${d.version}</span>
        <span>${escapeHtml(d.file_path || 'manual')}</span>
      </div>
    </li>
  `).join('');
}

function renderDocViewer() {
  const doc = state.selectedDoc;
  if (!doc) return;

  document.getElementById('doc-title-display').textContent = doc.title;
  document.getElementById('doc-meta-display').textContent = `File: ${doc.file_path || 'None'} • Version: v${doc.version} • Updated: ${formatTimestamp(doc.updated_at)}`;

  // Versions dropdown
  const verSelect = document.getElementById('doc-version-select');
  if (verSelect && doc.versions) {
    verSelect.innerHTML = doc.versions.map(v => `
      <option value="${v.version_num}">v${v.version_num} - ${escapeHtml(v.change_summary || 'Revision')}</option>
    `).join('');
  }

  // Render Markdown content
  const preview = document.getElementById('doc-content-rendered');
  if (preview) {
    preview.innerHTML = renderMarkdown(doc.content);
  }
}

function renderCodeAnalysis() {
  // Populate sample files dropdown
  const select = document.getElementById('sample-file-select');
  if (select && select.children.length === 0) {
    select.innerHTML = state.sampleFiles.map(s => `
      <option value="${s.filename}">${s.filename}</option>
    `).join('');
    select.addEventListener('change', (e) => selectSampleFile(e.target.value));
  }
}

function selectSampleFile(filename) {
  const sample = state.sampleFiles.find(s => s.filename === filename);
  if (!sample) return;
  state.selectedSample = sample;
  state.currentSourceCode = sample.content;

  const editor = document.getElementById('source-code-editor');
  if (editor) {
    editor.value = sample.content;
  }
  runAstAnalysis();
}

async function runAstAnalysis() {
  const editor = document.getElementById('source-code-editor');
  const code = editor ? editor.value : state.currentSourceCode;
  const filename = state.selectedSample ? state.selectedSample.filename : 'source.py';

  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ source_code: code, filename })
    });
    const data = await res.json();
    state.currentAst = data;
    renderAstResults(data);
  } catch (err) {
    console.error('Analysis failed:', err);
    showToast('AST Analysis failed');
  }
}

function renderAstResults(astData) {
  const container = document.getElementById('ast-results-container');
  if (!container) return;

  if (!astData.is_valid) {
    container.innerHTML = `
      <div style="padding: 16px; color: var(--status-fail);">
        <strong>Syntax Error:</strong> ${escapeHtml(astData.error)}
      </div>
    `;
    return;
  }

  const m = astData.metrics || {};
  let html = `
    <div style="display: flex; gap: 12px; margin-bottom: 16px; padding: 12px; background: var(--bg-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-light);">
      <div><strong>Symbols:</strong> ${m.total_symbols || 0}</div>
      <div><strong>Doc Coverage:</strong> <span class="badge ${m.doc_coverage_percent > 70 ? 'badge-pass' : 'badge-warn'}">${m.doc_coverage_percent || 0}%</span></div>
      <div><strong>Debt Items:</strong> ${m.undocumented_symbols || 0}</div>
    </div>
  `;

  // Classes
  if (astData.classes && astData.classes.length > 0) {
    html += `<h4 style="margin: 12px 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">Detected Classes</h4>`;
    astData.classes.forEach(c => {
      html += `
        <div class="symbol-tree-item">
          <div class="symbol-header">
            <span>class ${escapeHtml(c.name)} (${escapeHtml(c.bases.join(', ') || 'object')})</span>
            <span style="font-size: 11px; color: var(--text-faint);">L${c.line_start}-L${c.line_end}</span>
          </div>
          <div class="symbol-body">
            <div style="margin-bottom: 6px; color: var(--text-muted); font-size: 11px;">
              ${c.docstring ? escapeHtml(c.docstring) : '<span style="color: var(--status-fail);">⚠️ No docstring provided</span>'}
            </div>
            ${c.methods.map(method => `
              <div style="font-family: var(--font-mono); font-size: 11px; padding: 4px 0; border-top: 1px solid var(--border-subtle);">
                <strong>.${escapeHtml(method.name)}</strong>(${escapeHtml(method.parameters.map(p => p.name).join(', '))})${method.return_type ? ': ' + escapeHtml(method.return_type) : ''}
              </div>
            `).join('')}
          </div>
        </div>
      `;
    });
  }

  // Top-level functions
  if (astData.functions && astData.functions.length > 0) {
    html += `<h4 style="margin: 14px 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted);">Module Functions</h4>`;
    astData.functions.forEach(f => {
      html += `
        <div class="symbol-tree-item">
          <div class="symbol-header">
            <span>def ${escapeHtml(f.name)}(...)</span>
            <span style="font-size: 11px; color: var(--text-faint);">L${f.line_start}</span>
          </div>
          <div class="symbol-body" style="font-size: 11px; color: var(--text-muted);">
            ${f.docstring ? escapeHtml(f.docstring) : '<span style="color: var(--status-warn);">⚠️ Missing docstring</span>'}
          </div>
        </div>
      `;
    });
  }

  container.innerHTML = html;
}

// ==========================================
// 12-Stage Pipeline Execution
// ==========================================

async function triggerPipelineRun() {
  const editor = document.getElementById('source-code-editor');
  const code = editor ? editor.value : state.currentSourceCode;
  const filename = state.selectedSample ? state.selectedSample.filename : 'data_pipeline.py';

  showPipelineModal();
  updatePipelineModalStatus('Initiating HERMES 12-Stage Synchronization Pipeline...', []);

  try {
    const res = await fetch('/api/run-pipeline', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        source_code: code,
        filename: filename,
        title: filename.replace('.py', '').replace('_', ' ').title()
      })
    });
    const data = await res.json();
    if (data.success) {
      updatePipelineModalStatus('Pipeline Completed Successfully', data.stages, data);
      await fetchStats();
      await fetchDocuments();
      await fetchRuns();
      await fetchPullRequests();
      await fetchActivities();
      showToast('Documentation pipeline completed and PR staged!');
    } else {
      updatePipelineModalStatus('Pipeline Encountered Errors', data.stages || []);
    }
  } catch (err) {
    console.error('Pipeline execution failed:', err);
    updatePipelineModalStatus('Network or Subprocess Error', [{
      stage: 0,
      name: 'System Error',
      status: 'error',
      details: String(err)
    }]);
  }
}

function showPipelineModal() {
  let modal = document.getElementById('pipeline-modal');
  if (!modal) {
    modal = document.createElement('div');
    modal.id = 'pipeline-modal';
    modal.className = 'pipeline-modal-backdrop';
    modal.innerHTML = `
      <div class="pipeline-modal">
        <div class="modal-header">
          <div style="font-weight: 600; font-size: 14px; display: flex; align-items: center; gap: 8px;">
            <span class="brand-dot"></span>
            HERMES Automation Pipeline Monitor
          </div>
          <button class="btn btn-secondary btn-sm" onclick="closePipelineModal()">Close</button>
        </div>
        <div class="modal-body" id="pipeline-modal-body">
          <div style="color: var(--text-muted); font-size: 13px;">Executing pipeline stages...</div>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  }
  modal.style.display = 'flex';
}

function closePipelineModal() {
  const modal = document.getElementById('pipeline-modal');
  if (modal) modal.style.display = 'none';
}

function updatePipelineModalStatus(heading, stages, fullData = null) {
  const body = document.getElementById('pipeline-modal-body');
  if (!body) return;

  let html = `<div style="font-weight: 600; font-size: 15px; margin-bottom: 12px;">${escapeHtml(heading)}</div>`;
  html += stages.map(s => `
    <div class="stage-item">
      <span class="stage-badge ${s.status === 'success' ? 'badge-pass' : s.status === 'warning' ? 'badge-warn' : 'badge-fail'}">
        Stage ${s.stage}
      </span>
      <div style="flex: 1;">
        <div style="font-weight: 600; font-size: 13px;">${escapeHtml(s.name)}</div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(s.details)}</div>
      </div>
    </div>
  `).join('');

  if (fullData && fullData.pull_request) {
    const pr = fullData.pull_request;
    html += `
      <div style="margin-top: 14px; padding: 14px; background: var(--bg-subtle); border-radius: var(--radius-sm); border: 1px solid var(--border-light);">
        <div style="font-weight: 600; font-size: 13px; margin-bottom: 4px;">Proposed Pull Request</div>
        <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">
          Branch: <code style="font-family: var(--font-mono);">${pr.branch_name}</code>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-primary btn-sm" onclick="closePipelineModal(); switchTab('github');">View Staged PR</button>
          <button class="btn btn-secondary btn-sm" onclick="closePipelineModal(); switchTab('docs');">View Document</button>
        </div>
      </div>
    `;
  }

  body.innerHTML = html;
}

// ==========================================
// AI Assistant Interaction
// ==========================================

async function submitAssistantQuery() {
  const input = document.getElementById('assistant-input');
  const query = input ? input.value.trim() : '';
  if (!query) return;

  const chatHistory = document.getElementById('assistant-chat-history');
  
  // Append user bubble
  chatHistory.innerHTML += `
    <div class="chat-bubble chat-bubble-user">
      <div class="chat-meta">
        <strong>You</strong>
      </div>
      <div>${escapeHtml(query)}</div>
    </div>
  `;
  input.value = '';
  chatHistory.scrollTop = chatHistory.scrollHeight;

  // Append pending indicator
  const pendingId = 'pending-' + Date.now();
  chatHistory.innerHTML += `
    <div id="${pendingId}" class="chat-bubble chat-bubble-hermes">
      <div class="chat-meta">
        <span class="brand-dot"></span>
        <strong>HERMES Assistant</strong>
        <span>Searching repository & doc facts...</span>
      </div>
    </div>
  `;
  chatHistory.scrollTop = chatHistory.scrollHeight;

  try {
    const res = await fetch('/api/assistant/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query })
    });
    const data = await res.json();
    const pendingEl = document.getElementById(pendingId);
    if (pendingEl) {
      pendingEl.innerHTML = `
        <div class="chat-meta">
          <span class="brand-dot"></span>
          <strong>HERMES Project Assistant</strong>
          <span style="font-size: 10px; color: var(--text-faint);">${escapeHtml(data.engine || 'Grounded')}</span>
          ${data.source_references ? data.source_references.map(r => `<span class="source-pill">${escapeHtml(r)}</span>`).join('') : ''}
        </div>
        <div class="markdown-rendered">${renderMarkdown(data.response)}</div>
      `;
    }
  } catch (err) {
    const pendingEl = document.getElementById(pendingId);
    if (pendingEl) {
      pendingEl.innerHTML = `<span style="color: var(--status-fail);">Failed to contact assistant service.</span>`;
    }
  }
  chatHistory.scrollTop = chatHistory.scrollHeight;
}

// ==========================================
// Tests & Verification Panel
// ==========================================

function renderVerificationRuns() {
  const tbody = document.getElementById('runs-table-body');
  if (!tbody) return;

  if (state.verificationRuns.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-faint); padding: 24px;">No verification runs recorded.</td></tr>`;
    return;
  }

  tbody.innerHTML = state.verificationRuns.map(r => `
    <tr>
      <td style="font-family: var(--font-mono); font-size: 11px;">${escapeHtml(r.snippet_id)}</td>
      <td>${escapeHtml(r.document_title || 'Standalone')}</td>
      <td>
        <span class="badge ${r.status === 'Passed' ? 'badge-pass' : 'badge-fail'}">${r.status}</span>
        ${r.correction_attempts > 0 ? `<span class="badge badge-warn">${r.correction_attempts} loop(s)</span>` : ''}
      </td>
      <td style="font-family: var(--font-mono); font-size: 11px;">${r.execution_time_ms ? r.execution_time_ms + ' ms' : '—'}</td>
      <td>
        <div class="output-terminal">${escapeHtml(r.stdout || r.stderr || 'No output')}</div>
      </td>
      <td>
        ${r.status === 'Failed' ? `
          <button class="btn btn-secondary btn-sm" onclick="triggerCorrection('${escapeHtml(r.snippet_id)}')">
            Auto-Repair
          </button>
        ` : '—'}
      </td>
    </tr>
  `).join('');
}

async function triggerCorrection(snippetId) {
  const run = state.verificationRuns.find(r => r.snippet_id === snippetId);
  if (!run) return;

  showToast(`Initiating bounded correction loop for ${snippetId}...`);
  try {
    const res = await fetch('/api/correct', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        snippet_code: run.snippet_code,
        stderr: run.stderr,
        document_id: run.document_id,
        snippet_id: run.snippet_id
      })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Correction succeeded after ${data.attempts_taken} iteration(s)!`);
    } else {
      showToast('Correction loop terminated without clean pass.');
    }
    await fetchRuns();
    renderVerificationRuns();
  } catch (err) {
    console.error('Correction failed:', err);
    showToast('Correction request failed');
  }
}

// ==========================================
// Pull Requests Panel
// ==========================================

function renderPullRequests() {
  const container = document.getElementById('pr-list-container');
  if (!container) return;

  if (state.pullRequests.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-faint); padding: 32px;">No staged pull requests.</div>`;
    return;
  }

  container.innerHTML = state.pullRequests.map(pr => `
    <div class="card" style="margin-bottom: 16px;">
      <div class="card-title">
        <div>
          <span>#${pr.pr_number || 'PR'}</span> ${escapeHtml(pr.title)}
          <span class="badge ${pr.is_demo ? 'badge-warn' : 'badge-pass'}" style="margin-left: 8px;">
            ${pr.is_demo ? 'Local Simulation' : 'GitHub Live'}
          </span>
        </div>
        <div style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-teal);">
          ${escapeHtml(pr.branch_name)}
        </div>
      </div>
      <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 12px; white-space: pre-line;">
        ${escapeHtml(pr.summary)}
      </div>
      <div class="diff-viewer">
        ${renderDiff(pr.diff_content)}
      </div>
    </div>
  `).join('');
}

function renderDiff(diffText) {
  if (!diffText) return '<em>No diff content available</em>';
  return diffText.split('\n').map(line => {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      return `<div class="diff-add">${escapeHtml(line)}</div>`;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      return `<div class="diff-del">${escapeHtml(line)}</div>`;
    }
    return `<div>${escapeHtml(line)}</div>`;
  }).join('');
}

// ==========================================
// Activity Log Panel
// ==========================================

function renderActivities() {
  const container = document.getElementById('activity-list-container');
  if (!container) return;

  if (state.activities.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-faint); padding: 32px;">No activities recorded.</div>`;
    return;
  }

  container.innerHTML = state.activities.map(a => `
    <div style="display: flex; gap: 14px; padding: 14px 0; border-bottom: 1px solid var(--border-subtle);">
      <span class="badge ${a.severity === 'success' ? 'badge-pass' : a.severity === 'warning' ? 'badge-warn' : 'badge-neutral'}">
        ${escapeHtml(a.event_type)}
      </span>
      <div style="flex: 1;">
        <div style="font-weight: 600; font-size: 13px;">${escapeHtml(a.title)}</div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 2px;">${escapeHtml(a.description)}</div>
      </div>
      <div style="font-family: var(--font-mono); font-size: 11px; color: var(--text-faint);">
        ${formatTimestamp(a.created_at)}
      </div>
    </div>
  `).join('');
}

// ==========================================
// Settings Panel
// ==========================================

function renderSettings() {
  const s = state.settings;
  const provSelect = document.getElementById('settings-provider');
  if (provSelect) provSelect.value = s.api_provider || 'offline_engine';

  const timeoutInput = document.getElementById('settings-timeout');
  if (timeoutInput) timeoutInput.value = s.sandbox_timeout_seconds || '5.0';

  const maxAttempts = document.getElementById('settings-max-attempts');
  if (maxAttempts) maxAttempts.value = s.max_correction_attempts || '2';

  const repoInput = document.getElementById('settings-github-repo');
  if (repoInput) repoInput.value = s.github_repo || '';
}

async function saveSettings() {
  const payload = {
    api_provider: document.getElementById('settings-provider').value,
    sandbox_timeout_seconds: document.getElementById('settings-timeout').value,
    max_correction_attempts: document.getElementById('settings-max-attempts').value,
    github_repo: document.getElementById('settings-github-repo').value
  };

  const keyVal = document.getElementById('settings-api-key').value;
  if (keyVal.trim()) payload.api_key = keyVal.trim();

  const tokenVal = document.getElementById('settings-github-token').value;
  if (tokenVal.trim()) payload.github_token = tokenVal.trim();

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      showToast('Settings successfully updated');
      await fetchSettings();
    }
  } catch (err) {
    showToast('Failed to save settings');
  }
}

// ==========================================
// Helpers & Lightweight Markdown Parser
// ==========================================

function renderMarkdown(md) {
  if (!md) return '';
  let out = md;

  // Code blocks ```python ... ```
  out = out.replace(/```python\s*([\s\S]*?)```/g, (match, code) => {
    return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
  });
  out = out.replace(/```\s*([\s\S]*?)```/g, (match, code) => {
    return `<pre><code>${escapeHtml(code.trim())}</code></pre>`;
  });

  // Headers
  out = out.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  out = out.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  out = out.replace(/^# (.*$)/gim, '<h1>$1</h1>');

  // Blockquotes
  out = out.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Bold & inline code
  out = out.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  out = out.replace(/`([^`]+)`/g, '<code>$1</code>');

  // Links
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

  // Simple Markdown Tables
  const lines = out.split('\n');
  let inTable = false;
  let tableHtml = '';
  const newLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line.startsWith('|') && line.endsWith('|')) {
      if (!inTable) {
        inTable = true;
        tableHtml = '<table>';
      }
      if (line.includes('---')) {
        // Separator line
        continue;
      }
      const cells = line.split('|').filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      const isHeader = !tableHtml.includes('<tr>');
      const tag = isHeader ? 'th' : 'td';
      tableHtml += `<tr>${cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('')}</tr>`;
    } else {
      if (inTable) {
        tableHtml += '</table>';
        newLines.push(tableHtml);
        inTable = false;
        tableHtml = '';
      }
      if (line) {
        if (!line.startsWith('<h') && !line.startsWith('<pre') && !line.startsWith('<block')) {
          newLines.push(`<p>${line}</p>`);
        } else {
          newLines.push(line);
        }
      }
    }
  }
  if (inTable) {
    tableHtml += '</table>';
    newLines.push(tableHtml);
  }

  return newLines.join('\n');
}

function handleGlobalSearch(query) {
  if (!query.trim()) return;
  // If user searches globally, jump to docs or filter
  if (state.activeTab !== 'docs') {
    switchTab('docs');
  }
  const docSearchInput = document.getElementById('doc-search-input');
  if (docSearchInput) {
    docSearchInput.value = query;
    renderDocCatalog(query);
  }
}

function showToast(msg) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = 'toast';
  toast.textContent = msg;
  container.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 3500);
}

function formatTimestamp(ts) {
  if (!ts) return 'Just now';
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
