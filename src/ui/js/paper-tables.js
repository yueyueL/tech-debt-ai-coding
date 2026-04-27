/**
 * Paper Tables — Publication-ready statistics tables from aggregate_summary.json
 *
 * Renders detailed tables for each RQ with LaTeX copy support.
 */

function resolveDatasetName(defaultName = 'out') {
    const raw = new URLSearchParams(window.location.search).get('dataset') || defaultName;
    return /^[A-Za-z0-9._-]+$/.test(raw) ? raw : defaultName;
}

const PAPER_TABLES_DATASET = resolveDatasetName();
const AUTO_REFRESH_MS = 60000;
const TOOL_NAMES = {
    copilot: 'GitHub Copilot', claude: 'Claude', cursor: 'Cursor', gemini: 'Gemini',
    devin: 'Devin', aider: 'Aider', codex: 'OpenAI Codex', coderabbit: 'CodeRabbit',
    lovable: 'Lovable', bolt: 'Bolt', sweep: 'Sweep', codeium: 'Codeium',
    pieces: 'Pieces', tabnine: 'Tabnine', amazon_q: 'Amazon Q', openhands: 'OpenHands',
    codeflash: 'CodeFlash', codegen: 'Codegen', sourcery: 'Sourcery', continue: 'Continue',
    deepsource: 'DeepSource', ellipsis: 'Ellipsis', gitauto: 'GitAuto', penify: 'Penify',
};
let _liveRefreshSupported = false;
let _refreshTimer = null;
let _refreshInFlight = false;
const SECURITY_RULE_LABELS = {
    B101: 'Assert Used', B102: 'exec() Used', B103: 'Permissive File Permissions',
    B104: 'Binding to All Interfaces', B105: 'Hardcoded Password (arg)',
    B106: 'Hardcoded Password (func)', B107: 'Hardcoded Password (default)',
    B108: 'Insecure Temp File', B110: 'Try-Except-Pass', B112: 'Try-Except-Continue',
    B113: 'Requests Without Timeout', B201: 'Flask Debug Mode',
    B202: 'Unsafe tarfile.extractall', B301: 'Pickle Deserialization',
    B307: 'Unsafe eval-like Function', B310: 'Unsafe URL Open',
    B311: 'Insecure Random Generator', B314: 'Unsafe XML Parsing',
    B324: 'Weak Hash (MD5/SHA1)', B403: 'Pickle Import', B404: 'Subprocess Import',
    B501: 'SSL verify=False', B506: 'Unsafe YAML Load',
    B602: 'Subprocess with shell=True', B603: 'Subprocess Without Shell Check',
    B604: 'Function with shell=True', B605: 'Process with Shell',
    B607: 'Partial Executable Path', B608: 'SQL Injection via String Format',
    B614: 'Unsafe PyTorch Load', B615: 'Unsafe HuggingFace Hub Download',
    B701: 'Jinja2 Autoescape Disabled',
};
// Human-readable labels for Semgrep rule IDs. Keys are the raw dot-notation
// rule IDs emitted by semgrep; values are short phrases for display.
const SEMGREP_RULE_LABELS = {
    'javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal': 'Path traversal via path.join/resolve',
    'javascript.lang.security.audit.unsafe-formatstring.unsafe-formatstring': 'Unsafe format string',
    'javascript.lang.security.audit.detect-non-literal-regexp.detect-non-literal-regexp': 'Non-literal regular expression',
    'javascript.lang.security.detect-child-process.detect-child-process': 'Child process execution',
    'javascript.lang.security.audit.prototype-pollution.prototype-pollution-loop.prototype-pollution-loop': 'Prototype pollution via loop',
    'javascript.lang.security.audit.spawn-shell-true.spawn-shell-true': 'spawn() with shell=true',
    'javascript.lang.security.audit.incomplete-sanitization.incomplete-sanitization': 'Incomplete input sanitization',
    'javascript.lang.security.detect-insecure-websocket.detect-insecure-websocket': 'Insecure WebSocket (ws://)',
    'javascript.express.security.audit.xss.direct-response-write.direct-response-write': 'XSS via direct response.write',
    'javascript.express.security.injection.raw-html-format.raw-html-format': 'Raw HTML injection (XSS risk)',
    'javascript.browser.security.wildcard-postmessage-configuration.wildcard-postmessage-configuration': 'Wildcard postMessage origin',
    'python.lang.security.dangerous-globals-use.dangerous-globals-use': 'Dangerous Python global access',
    'python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query': 'SQLAlchemy raw query execution',
    'python.sqlalchemy.security.audit.avoid-sqlalchemy-text.avoid-sqlalchemy-text': 'Raw SQLAlchemy text() query',
    'python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure': 'Credentials leaked to logger',
    'python.lang.security.deserialization.pickle.avoid-pickle': 'Unsafe pickle deserialization',
    'python.flask.security.xss.audit.direct-use-of-jinja2.direct-use-of-jinja2': 'Direct use of Jinja2 (XSS)',
    'python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected': 'Dynamic urllib request (SSRF)',
    'python.lang.security.audit.non-literal-import.non-literal-import': 'Non-literal import (arbitrary code)',
    'python.lang.security.audit.formatted-sql-query.formatted-sql-query': 'Formatted SQL query (SQL injection)',
    'python.lang.security.audit.subprocess-shell-true.subprocess-shell-true': 'Subprocess with shell=True',
    'python.lang.security.audit.eval-detected.eval-detected': 'eval() usage',
    'python.lang.security.audit.exec-detected.exec-detected': 'exec() usage',
    'python.lang.security.use-defused-xml.use-defused-xml': 'Unsafe XML parsing (use defusedxml)',
    'python.lang.security.use-defused-xml-parse.use-defused-xml-parse': 'Unsafe XML parse (use defusedxml)',
    'trailofbits.python.pickles-in-pytorch.pickles-in-pytorch': 'Pickle load in PyTorch',
    'trailofbits.python.numpy-in-pytorch-modules.numpy-in-pytorch-modules': 'NumPy inside PyTorch module',
    'trailofbits.python.automatic-memory-pinning.automatic-memory-pinning': 'PyTorch automatic memory pinning',
    'problem-based-packs.insecure-transport.js-node.bypass-tls-verification.bypass-tls-verification': 'TLS verification bypass',
};
const RULE_LABEL_OVERRIDES = {
    'broad-exception-caught': 'Broad exception handling',
    'protected-access': 'Access to protected member',
    'unused-import': 'Unused import',
    'unused-argument': 'Unused argument',
    'unused-variable': 'Unused local variable',
    'redefined-outer-name': 'Shadowed outer variable',
    'undefined-variable': 'Undefined variable or reference',
    'possibly-used-before-assignment': 'Possibly used before assignment',
    'attribute-defined-outside-init': 'Attribute defined outside initializer',
    'raise-missing-from': 'Missing exception chaining',
    'too-many-branches': 'Too many branches',
    'too-many-statements': 'Too many statements',
    'too-many-arguments': 'Too many parameters',
    'too-many-locals': 'Too many local variables',
    'too-few-public-methods': 'Too few public methods',
    'missing-function-docstring': 'Missing function docstring',
    'missing-module-docstring': 'Missing module docstring',
    'missing-class-docstring': 'Missing class docstring',
    'line-too-long': 'Overlong line',
    'trailing-whitespace': 'Trailing whitespace',
    'invalid-name': 'Non-descriptive or invalid name',
    'logging-fstring-interpolation': 'Logging f-string interpolation',
    'import-outside-toplevel': 'Import outside top level',
    'f-string-without-interpolation': 'F-string without interpolation',
    'no-invalid-this': 'Invalid `this` usage',
    'no-useless-escape': 'Unnecessary escape sequence',
    'new-cap': 'Constructor naming mismatch',
    'block-scoped-var': 'Block-scoped variable misuse',
    'eqeqeq': 'Loose equality comparison',
    'function-redefined': 'Redeclared function or symbol',
    'no-redeclare': 'Redeclared symbol',
    'no-self-compare': 'Self comparison',
    'no-constant-binary-expression': 'Constant binary expression',
    'no-unused-vars': 'Unused variables or parameters',
    '@typescript-eslint/no-unused-vars': 'Unused variables or parameters',
    'no-undef': 'Undefined variable or reference',
    'unreachable': 'Unreachable code',
    'no-unreachable': 'Unreachable code',
    'no-shadow': 'Shadowed outer variable',
    '@typescript-eslint/no-shadow': 'Shadowed outer variable',
    'max-params': 'Too many parameters',
    '@typescript-eslint/max-params': 'Too many parameters',
    'no-magic-numbers': 'Magic numbers',
    '@typescript-eslint/no-magic-numbers': 'Magic numbers',
    '@typescript-eslint/array-type': 'Inconsistent array type syntax',
    '@typescript-eslint/consistent-type-definitions': 'Inconsistent type definition style',
    '@typescript-eslint/parameter-properties': 'Parameter properties in constructor',
    '@typescript-eslint/explicit-function-return-type': 'Missing explicit function return type',
    '@typescript-eslint/explicit-member-accessibility': 'Missing explicit member accessibility',
    '@typescript-eslint/explicit-module-boundary-types': 'Missing explicit module boundary types',
    '@typescript-eslint/no-explicit-any': 'Use of `any` type',
    'sort-keys': 'Unsorted object keys',
    'one-var': 'Multiple variables in one declaration',
    'id-length': 'Very short identifier names',
    'no-var': 'Use of `var`',
};
const RULE_GROUPS = [
    { key: 'unused-vars', label: 'Unused variables or parameters', rawRules: ['no-unused-vars', '@typescript-eslint/no-unused-vars'] },
    { key: 'undefined-reference', label: 'Undefined variable or reference', rawRules: ['undefined-variable', 'no-undef'] },
    { key: 'unreachable-code', label: 'Unreachable code', rawRules: ['unreachable', 'no-unreachable'] },
    { key: 'shadowed-variable', label: 'Shadowed outer variable', rawRules: ['redefined-outer-name', 'no-shadow', '@typescript-eslint/no-shadow'] },
    { key: 'too-many-params', label: 'Too many parameters', rawRules: ['too-many-arguments', 'max-params', '@typescript-eslint/max-params'] },
    { key: 'redeclared-symbol', label: 'Redeclared symbol', rawRules: ['function-redefined', 'no-redeclare'] },
    { key: 'magic-numbers', label: 'Magic numbers', rawRules: ['no-magic-numbers', '@typescript-eslint/no-magic-numbers'] },
];
const RULE_GROUP_LOOKUP = Object.fromEntries(
    RULE_GROUPS.flatMap(group => group.rawRules.map(rule => [rule, group]))
);

function toolName(key) { return TOOL_NAMES[key] || key; }
function fmt(n) { return typeof n === 'number' ? n.toLocaleString() : (n || '—'); }
function fmtPct(n) { return typeof n === 'number' ? n.toFixed(1) + '%' : '—'; }
function fmtDec(n, d = 2) { return typeof n === 'number' ? n.toFixed(d) : '—'; }
function humanizeRuleId(rule) {
    const raw = String(rule || '').trim();
    if (!raw) return 'Unknown rule';
    // ESLint plugin namespace: "@typescript-eslint/no-shadow" → "no-shadow"
    let base = raw.includes('/') ? raw.split('/').pop() : raw;
    // Semgrep uses dot-notation rule IDs, e.g. "javascript.lang.security.audit.xxx.yyy.yyy".
    // Take the last segment as the rule slug, and collapse a trailing duplicate
    // (Semgrep often ends with ".foo.foo" where the last two segments are identical).
    if (base.includes('.')) {
        const parts = base.split('.').filter(Boolean);
        if (parts.length >= 2 && parts[parts.length - 1] === parts[parts.length - 2]) parts.pop();
        base = parts[parts.length - 1] || raw;
    }
    const cleaned = base.replace(/[_-]+/g, ' ').trim();
    return cleaned ? cleaned.charAt(0).toUpperCase() + cleaned.slice(1) : raw;
}
function canonicalRuleInfo(rule, description = '') {
    const raw = String(rule || '').trim();
    const grouped = RULE_GROUP_LOOKUP[raw];
    if (grouped) {
        return { key: grouped.key, label: grouped.label };
    }
    const label = description
        || SECURITY_RULE_LABELS[raw]
        || SEMGREP_RULE_LABELS[raw]
        || RULE_LABEL_OVERRIDES[raw]
        || humanizeRuleId(raw);
    return { key: raw || '?', label };
}
function mergeRuleRows(rows, {
    ruleField = 'name',
    countField = 'count',
    sortField = 'count',
    limit = 10,
    totalCount = 0,
    filteredTotal = 0,
} = {}) {
    const merged = new Map();
    for (const row of rows || []) {
        const rawRule = row?.[ruleField] || row?.name || row?.rule || '?';
        const info = canonicalRuleInfo(rawRule, row?.description || '');
        if (!merged.has(info.key)) {
            merged.set(info.key, {
                key: info.key,
                label: info.label,
                raw_rules: new Set(),
                count: 0,
                high: 0,
                medium: 0,
                low: 0,
                surviving: 0,
                total: 0,
                share_pct: 0,
                filtered_share_pct: 0,
                rate: 0,
            });
        }
        const entry = merged.get(info.key);
        entry.raw_rules.add(rawRule);
        entry.count += Number(row?.[countField] || row?.count || 0);
        entry.high += Number(row?.high || 0);
        entry.medium += Number(row?.medium || 0);
        entry.low += Number(row?.low || 0);
        entry.surviving += Number(row?.surviving || 0);
        entry.total += Number(row?.total || row?.total_tracked || 0);
    }
    const rowsOut = [...merged.values()].map(entry => {
        const rawRules = [...entry.raw_rules].sort();
        return {
            ...entry,
            raw_rules: rawRules,
            rate: entry.total > 0 ? entry.surviving / entry.total : 0,
            share_pct: totalCount > 0 ? entry.count / totalCount * 100 : 0,
            filtered_share_pct: filteredTotal > 0 ? entry.count / filteredTotal * 100 : 0,
        };
    });
    rowsOut.sort((a, b) => (b[sortField] || 0) - (a[sortField] || 0));
    return rowsOut.slice(0, limit);
}
function normalizeFamilyData(byFamily) {
    const norm = {};
    for (const [family, raw] of Object.entries(byFamily || {})) {
        if (typeof raw === 'number') {
            norm[family] = { issues: raw, fixed: 0, net: raw, repos: 0, commits: 0 };
        } else {
            norm[family] = {
                issues: raw?.issues || raw?.count || 0,
                fixed: raw?.fixed || 0,
                net: raw?.net ?? ((raw?.issues || 0) - (raw?.fixed || 0)),
                repos: raw?.repos || 0,
                commits: raw?.commits || 0,
            };
        }
    }
    return norm;
}

function collectMergedRuleNotes(sectionRows) {
    const notes = new Map();
    for (const row of sectionRows.flat()) {
        if ((row.raw_rules || []).length <= 1) continue;
        if (!notes.has(row.key)) {
            notes.set(row.key, { label: row.label, raw_rules: row.raw_rules });
        }
    }
    return [...notes.values()].sort((a, b) => a.label.localeCompare(b.label));
}

function datasetQuery(extra = '') {
    if (PAPER_TABLES_DATASET === 'out') return extra ? `?${extra}` : '';
    const datasetParam = `dataset=${encodeURIComponent(PAPER_TABLES_DATASET)}`;
    return extra ? `?${extra}&${datasetParam}` : `?${datasetParam}`;
}
function appendDatasetToHref(href) {
    if (!href || href.includes('dataset=')) return href;
    const datasetParam = `dataset=${encodeURIComponent(PAPER_TABLES_DATASET)}`;
    return href.includes('?') ? `${href}&${datasetParam}` : `${href}?${datasetParam}`;
}
function applyDatasetLinks() {
    document.querySelectorAll('[data-preserve-dataset="true"]').forEach(anchor => {
        const href = anchor.getAttribute('href');
        if (!href || href.startsWith('#') || PAPER_TABLES_DATASET === 'out') return;
        anchor.setAttribute('href', appendDatasetToHref(href));
    });
}

/** Normalize raw survival severity keys to high/medium/low */
function normalizeSurvivalSeverity(bySev) {
    const norm = { high: {total:0,surviving:0}, medium: {total:0,surviving:0}, low: {total:0,surviving:0} };
    const mapping = { ERROR:'high', FATAL:'high', HIGH:'high', WARNING:'medium', MEDIUM:'medium',
                      CONVENTION:'low', REFACTOR:'low', LOW:'low', INFO:'low' };
    for (const [key, data] of Object.entries(bySev || {})) {
        const bucket = mapping[key.toUpperCase()] || 'low';
        norm[bucket].total += (data.total || 0);
        norm[bucket].surviving += (data.surviving || 0);
    }
    for (const s of Object.values(norm)) { s.fixed = s.total - s.surviving; s.rate = s.total > 0 ? s.surviving / s.total : 0; }
    return norm;
}

/** Focused data helpers — use top 5 tools data when available */
function _ft(data) { return (data.focused || {}).totals || data.totals; }
function _fsurv(data) { return (data.focused || {}).survival || data.rq3_survival; }
function _frole(data) { return (data.focused || {}).by_role || data.by_role || {}; }
function _ffile(data) { return (data.focused || {}).file_lifecycle || data.file_lifecycle || {}; }
function _ffilter(data) { return (data.focused || {}).filtering || data.false_positive_patterns || {}; }
function _frq1(data) {
    const f = data.focused;
    if (!f) {
        const gt = data.totals || {};
        return {
            by_severity: gt.actionable_by_severity || data.rq1_debt_types.by_severity,
            by_family: data.rq1_debt_types.by_family || {},
            by_language: gt.actionable_by_language || data.rq1_debt_types.by_language,
            top_rules: data.rq1_debt_types.top_rules,
            security_total: data.rq1_debt_types.security_total,
        };
    }
    const ft = f.totals || {};
    return { by_severity: ft.actionable_by_severity || f.by_severity, by_family: f.by_family || {}, by_language: f.by_language, top_rules: f.top_rules, security_total: f.security_total };
}
function _ftools(data) { return (data.focused || {}).by_tool || data.rq2_tool_comparison.by_tool; }

// ── Data Loading ──

async function loadData() {
    const refreshMeta = await refreshAggregateMetadata();
    const data = await loadAggregateFile();
    if (data) data._refresh_meta = refreshMeta;
    return data;
}

async function refreshAggregateMetadata() {
    try {
        const r = await fetch(`/__refresh_aggregate__${datasetQuery()}`, { cache: 'no-store' });
        if (!r.ok) return null;
        const payload = await r.json();
        if (!payload || !payload.ok) return null;
        _liveRefreshSupported = true;
        return payload;
    } catch (e) {
        return null;
    }
}

async function loadAggregateFile() {
    const paths = [
        `/results/${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `../../results/${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `../results/${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `results/${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `/${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `../../${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `../${PAPER_TABLES_DATASET}/aggregate_summary.json`,
        `${PAPER_TABLES_DATASET}/aggregate_summary.json`,
    ];
    for (const p of paths) {
        try {
            const r = await fetch(p, { cache: 'no-store' });
            if (r.ok) return await r.json();
        } catch (e) {
            /* next */
        }
    }
    return null;
}

function updateDataStatusBanner(data, refreshMeta = null) {
    const el = document.getElementById('data-status-banner');
    if (!el) return;
    const refreshedAt = refreshMeta?.aggregate_mtime
        ? new Date(refreshMeta.aggregate_mtime * 1000).toLocaleString()
        : (data?._generated_at || '?');
    const refreshMode = _liveRefreshSupported
        ? `Auto-refresh checks every ${Math.round(AUTO_REFRESH_MS / 1000)}s`
        : 'Static snapshot';
    el.textContent = `Dataset: ${PAPER_TABLES_DATASET}. Aggregate updated: ${refreshedAt}. ${refreshMode}. Counts may change while ${PAPER_TABLES_DATASET}/ is still being written.`;
}

// ── LaTeX Export ──

function copyLatex(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const rows = Array.from(table.querySelectorAll('tr'));
    const lines = [];
    let colCount = 0;

    rows.forEach((row, idx) => {
        const cells = Array.from(row.querySelectorAll('th, td'));
        if (idx === 0) colCount = cells.length;
        const vals = cells.map(c => c.textContent.trim().replace(/%/g, '\\%').replace(/&/g, '\\&').replace(/_/g, '\\_'));
        lines.push(vals.join(' & ') + ' \\\\');
        if (idx === 0) lines.push('\\midrule');
    });

    const colSpec = 'l' + 'r'.repeat(colCount - 1);
    const latex = `\\begin{table}[h]\n\\centering\n\\caption{TODO}\n\\label{tab:TODO}\n\\begin{tabular}{${colSpec}}\n\\toprule\n${lines.join('\n')}\n\\bottomrule\n\\end{tabular}\n\\end{table}`;

    navigator.clipboard.writeText(latex).then(() => {
        const btn = event.target;
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => { btn.textContent = 'Copy LaTeX'; btn.classList.remove('copied'); }, 2000);
    });
}

// ── Table Builders ──

function buildTableHTML(headers, rows, footerRow = null) {
    let html = '<table class="paper-table"><thead><tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr></thead><tbody>';
    for (const row of rows) {
        const cls = row._class || '';
        html += `<tr class="${cls}">` + row.cells.map(c => {
            const tdCls = (c.class || '') + (c.num ? ' num' : '');
            return `<td class="${tdCls}">${c.v}</td>`;
        }).join('') + '</tr>';
    }
    html += '</tbody>';
    if (footerRow) {
        html += '<tfoot><tr>' + footerRow.map(c => `<td class="${c.num ? 'num' : ''}">${c.v}</td>`).join('') + '</tr></tfoot>';
    }
    html += '</table>';
    return html;
}

function cell(v, num = false, cls = '') { return { v, num, class: cls }; }

// ── Render Functions ──

function renderDatasetStats(data) {
    const t = _ft(data);
    const toolCount = Object.keys(_ftools(data)).length;
    const issueTotal = t.actionable_introduced || t.issues_introduced;
    document.getElementById('dataset-stats').innerHTML = [
        `<div class="stat-mini"><div class="stat-mini-value">${fmt(t.repos)}</div><div class="stat-mini-label">Repositories</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${fmt(t.commits)}</div><div class="stat-mini-label">AI Commits</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${toolCount}</div><div class="stat-mini-label">Coding Tools</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${fmt(issueTotal)}</div><div class="stat-mini-label">Issues Found</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${fmt(t.files_analyzed)}</div><div class="stat-mini-label">Files Analyzed</div></div>`,
        `<div class="stat-mini"><div class="stat-mini-value">${fmtDec(t.fix_rate, 1)}%</div><div class="stat-mini-label">Fix Rate</div></div>`,
    ].join('');
}

function renderDatasetToolTable(data) {
    const byTool = _ftools(data);
    const sorted = Object.entries(byTool).sort((a, b) => b[1].commits - a[1].commits);

    const headers = ['Coding Tool', 'Commits', 'Repos', 'Issues', 'Issues/Commit', 'HIGH %', 'Security %', 'Zero-Issue %'];
    const rows = sorted.map(([key, t]) => {
        const actionable = t.actionable_issues || t.issues_total;
        const repos = t.repos_with_code || t.repos || 0;
        const ipc = t.commits > 0 ? (actionable / t.commits).toFixed(2) : '0';
        return {
            cells: [
                cell(toolName(key)), cell(fmt(t.commits), true),
                cell(fmt(repos), true),
                cell(fmt(actionable), true), cell(fmtDec(Number(ipc)), true),
                cell(fmtPct(t.high_pct), true), cell(fmtPct(t.security_pct), true),
                cell(fmtPct(t.zero_issue_pct), true),
            ]
        };
    });

    const totals = _ft(data);
    const footer = [
        cell('Total', false, 'bold'), cell(fmt(totals.commits), true),
        cell(fmt(totals.repos_with_code || totals.repos), true),
        cell(fmt(totals.actionable_introduced || totals.issues_introduced), true), cell('—', true),
        cell('—', true), cell('—', true), cell('—', true),
    ];

    document.getElementById('dataset-tool-table').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderDatasetLangTable(data) {
    const byLang = _frq1(data).by_language || {};
    const sorted = Object.entries(byLang).sort((a, b) => b[1] - a[1]).slice(0, 15);
    const totalIssues = _ft(data).actionable_introduced || _ft(data).issues_introduced;

    const headers = ['Language', 'Issues', '% of Total'];
    const rows = sorted.map(([lang, count]) => ({
        cells: [cell(lang || 'Unknown'), cell(fmt(count), true), cell(fmtPct(count / totalIssues * 100), true)]
    }));

    document.getElementById('dataset-lang-table').innerHTML = buildTableHTML(headers, rows);
}

function renderMonthlyDistribution(data) {
    // Use focused time_series (filtered to top 5 tools + study period)
    const ts = (data.focused && data.focused.time_series) ? data.focused.time_series : (data.time_series || []);
    if (!ts.length) return;

    const totalCommits = ts.reduce((s, r) => s + (r.commits || 0), 0);
    const sorted = [...ts].sort((a, b) => (a.month < b.month ? 1 : -1));

    const headers = ['Month', 'Commits', 'Share %'];
    const rows = sorted.map(r => {
        const commits = r.commits || 0;
        const share = totalCommits > 0 ? (commits / totalCommits * 100) : 0;
        return { cells: [cell(r.month), cell(fmt(commits), true), cell(fmtPct(share), true)] };
    });

    const footer = [cell('Total', false, 'bold'), cell(fmt(totalCommits), true), cell('100.0%', true)];
    document.getElementById('dataset-monthly-table').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderRQ1Family(data) {
    const fam = normalizeFamilyData((data.focused || {}).by_family || _frq1(data).by_family || {});
    const totalIntro = Object.values(fam).reduce((s, r) => s + (r.issues || 0), 0);
    const totalFixed = Object.values(fam).reduce((s, r) => s + (r.fixed || 0), 0);

    const headers = ['Issue Family', 'Introduced', 'Fixed', 'Net', 'Repos', 'Commits', '% of Total'];
    const rows = ['bug', 'code_smell', 'security'].filter(k => fam[k]?.issues).map(k => {
        const intro = fam[k].issues || 0;
        const fixed = fam[k].fixed || 0;
        const net = intro - fixed;
        const netCls = net > 0 ? 'highlight-worst' : net < 0 ? 'highlight-best' : '';
        return {
            cells: [
                cell(k.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())),
                cell(fmt(intro), true),
                cell(fmt(fixed), true),
                cell((net > 0 ? '+' : '') + fmt(net), true, netCls),
                cell(fmt(fam[k].repos || 0), true),
                cell(fmt(fam[k].commits || 0), true),
                cell(fmtPct(totalIntro > 0 ? intro / totalIntro * 100 : 0), true),
            ]
        };
    });

    const totalNet = totalIntro - totalFixed;
    const footer = [
        cell('Total', false, 'bold'), cell(fmt(totalIntro), true), cell(fmt(totalFixed), true),
        cell((totalNet > 0 ? '+' : '') + fmt(totalNet), true),
        cell('—', true), cell('—', true), cell('100.0%', true),
    ];
    document.getElementById('rq1-severity-table').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderRQ1FamilyRules(data) {
    const f = data.focused || {};
    const rulesByFamily = f.top_rules_by_family || {};

    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem;">';
    for (const fam of ['bug', 'code_smell', 'security']) {
        const rules = mergeRuleRows(rulesByFamily[fam] || [], { limit: 10 });
        if (!rules.length) continue;
        const label = fam === 'code_smell' ? 'Code Smell' : fam.charAt(0).toUpperCase() + fam.slice(1);
        html += '<div>';
        html += '<h4 style="margin:0 0 0.5rem;font-size:0.85rem;">' + label + '</h4>';
        html += '<table class="paper-table"><tr><th>#</th><th>Rule</th><th>Count</th></tr>';
        rules.forEach((r, i) => {
            html += '<tr><td>' + (i+1) + '</td><td>' + r.label + '</td><td style="text-align:right">' + fmt(r.count) + '</td></tr>';
        });
        html += '</table></div>';
    }
    html += '</div>';
    document.getElementById('rq1-family-rules-table').innerHTML = html;
}

function renderRQ1LanguageRules(data) {
    const f = data.focused || {};
    const rulesByLang = f.top_rules_by_language || {};
    const famByLang = f.family_by_language || {};

    let html = '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem;">';
    for (const lang of ['python', 'javascript']) {
        const rules = mergeRuleRows(rulesByLang[lang] || [], { limit: 10 });
        const fam = famByLang[lang] || {};
        const label = lang === 'javascript' ? 'JavaScript / TypeScript' : 'Python';
        const totalLang = Object.values(fam).reduce((s, v) => s + v, 0);
        html += '<div>';
        html += '<h4 style="margin:0 0 0.3rem;font-size:0.85rem;">' + label + ' (' + fmt(totalLang) + ' issues)</h4>';
        html += '<div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:0.5rem;">';
        const bld = f.by_language_breakdown || [];
        const langCommits = lang === 'javascript'
            ? (bld.find(b => b.language === 'JavaScript')?.commits || 0) + (bld.find(b => b.language === 'TypeScript')?.commits || 0)
            : (bld.find(b => b.language === 'Python')?.commits || 0);
        html += fmt(totalLang) + ' actionable issues across ' + fmt(langCommits) + ' commits';
        html += '</div>';
        html += '<table class="paper-table"><tr><th>#</th><th>Rule</th><th>Count</th></tr>';
        rules.forEach((r, i) => {
            html += '<tr><td>' + (i+1) + '</td><td>' + r.label + '</td><td style="text-align:right">' + fmt(r.count) + '</td></tr>';
        });
        html += '</table></div>';
    }
    html += '</div>';
    document.getElementById('rq1-lang-rules-table').innerHTML = html;
}

function renderRQ1FamilyByLanguage(data) {
    const f = data.focused || {};
    const famByLang = f.family_by_language || {};
    const breakdown = f.by_language_breakdown || [];

    // Build lookup for commits per language
    const langCommits = {};
    for (const b of breakdown) langCommits[b.language] = b.commits || 0;

    const langs = ['python', 'javascript'];
    const langLabels = { python: 'Python', javascript: 'JS / TS' };
    const families = ['bug', 'code_smell', 'security'];
    const famLabels = { bug: 'Bug', code_smell: 'Code Smell', security: 'Security' };

    // Headers: Family | Py Count | Py Rate | JS/TS Count | JS/TS Rate | Total
    const headers = ['Family', 'Python', 'Py /Commit', 'JS/TS', 'JS/TS /Commit', 'Total', '% of All'];
    const grandTotal = families.reduce((s, fam) =>
        s + langs.reduce((ss, l) => ss + ((famByLang[l] || {})[fam] || 0), 0), 0);

    const rows = families.map(fam => {
        const pyCount = (famByLang.python || {})[fam] || 0;
        const jsCount = (famByLang.javascript || {})[fam] || 0;
        const total = pyCount + jsCount;
        const pyCommits = langCommits.python || 1;
        const jsCommits = langCommits.javascript || 1;
        return { cells: [
            cell(famLabels[fam] || fam),
            cell(fmt(pyCount), true),
            cell(fmtDec(pyCount / pyCommits), true),
            cell(fmt(jsCount), true),
            cell(fmtDec(jsCount / jsCommits), true),
            cell(fmt(total), true),
            cell(fmtPct(grandTotal > 0 ? total / grandTotal * 100 : 0), true),
        ]};
    });

    const pyTotal = langs.reduce((s, l) => l === 'python' ? s + Object.values(famByLang[l] || {}).reduce((a, v) => a + v, 0) : s, 0);
    const jsTotal = Object.values(famByLang.javascript || {}).reduce((a, v) => a + v, 0);
    const footer = [
        cell('Total', false, 'bold'),
        cell(fmt(pyTotal), true), cell(fmtDec(pyTotal / (langCommits.python || 1)), true),
        cell(fmt(jsTotal), true), cell(fmtDec(jsTotal / (langCommits.javascript || 1)), true),
        cell(fmt(grandTotal), true), cell('100.0%', true),
    ];

    document.getElementById('rq1-family-lang-table').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderRQ1Type(data) {
    const byType = _frq1(data).by_family || {};
    const total = _ft(data).actionable_introduced || _ft(data).issues_introduced;
    const labelMap = { code_smell: 'Code Smell', bug: 'Bug', security: 'Security' };
    const order = ['code_smell', 'bug', 'security'];
    const sorted = order.filter(k => byType[k]).map(k => [k, byType[k]]);

    const headers = ['Issue Family', 'Count', '% of Total'];
    const rows = sorted.map(([type, count]) => ({
        cells: [cell(labelMap[type] || type), cell(fmt(count), true), cell(fmtPct(count / total * 100), true)]
    }));

    document.getElementById('rq1-type-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ1Rules(data) {
    const rules = mergeRuleRows(_frq1(data).top_rules || [], { sortField: 'count', limit: 20 });

    const headers = ['#', 'Rule', 'Count', 'HIGH', 'MEDIUM', 'LOW'];
    const rows = rules.map((r, i) => ({
        cells: [
            cell(i + 1, true), cell(r.label),
            cell(fmt(r.count), true),
            cell(fmt(r.high || 0), true), cell(fmt(r.medium || 0), true), cell(fmt(r.low || 0), true),
        ]
    }));

    document.getElementById('rq1-rules-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ1Role(data) {
    const br = _frole(data);
    const sole = br.sole_author || {};
    const co = br.coauthor || {};
    const all = _ft(data);

    const headers = ['Metric', 'All', 'Sole Author', 'Co-Author'];
    const metrics = [
        ['Commits', fmt(all.commits), fmt(sole.commits || 0), fmt(co.commits || 0)],
        ['Issues Introduced', fmt(all.issues_introduced), fmt(sole.issues || 0), fmt(co.issues || 0)],
        ['Issues Fixed', fmt(all.issues_fixed), fmt(sole.issues_fixed || 0), fmt(co.issues_fixed || 0)],
        ['Net Debt', fmt(all.net_debt), fmt(sole.net_debt || 0), fmt(co.net_debt || 0)],
        ['Issues/Commit', fmtDec(all.issues_introduced / all.commits), fmtDec(sole.issues_per_commit || 0), fmtDec(co.issues_per_commit || 0)],
        ['HIGH Issues', fmt(all.issues_introduced > 0 ? '—' : 0), fmt(sole.issues_high || 0), fmt(co.issues_high || 0)],
        ['Security Issues', '—', fmt(sole.issues_security || 0), fmt(co.issues_security || 0)],
        ['Files/Commit', fmtDec(all.files_per_commit), fmtDec(sole.files_per_commit || 0), fmtDec(co.files_per_commit || 0)],
        ['Issues/File', fmtDec(all.issues_per_file), fmtDec(sole.issues_per_file || 0), fmtDec(co.issues_per_file || 0)],
    ];

    const rows = metrics.map(m => ({
        cells: [cell(m[0]), cell(m[1], true), cell(m[2], true), cell(m[3], true)]
    }));

    document.getElementById('rq1-role-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ1ByStars(data) {
    const stars = (data.focused || {}).by_stars || [];
    if (!stars.length) return;
    const headers = ['Star Range', 'Repos', 'Commits', 'Bug/Commit', 'Smell/Commit', 'Security/Commit', 'Total/Commit'];
    const rows = stars.map(s => ({
        cells: [
            cell(s.label), cell(fmt(s.repos), true), cell(fmt(s.commits), true),
            cell(fmtDec(s.bugs_per_commit, 3), true),
            cell(fmtDec(s.smells_per_commit, 3), true),
            cell(fmtDec(s.security_per_commit, 3), true),
            cell(fmtDec(s.total_per_commit, 3), true),
        ]
    }));
    document.getElementById('rq1-by-stars-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ1ByLanguage(data) {
    const langs = (data.focused || {}).by_language_breakdown || [];
    if (!langs.length) return;
    const headers = ['Language', 'Repos', 'Commits', 'Bug/Commit', 'Smell/Commit', 'Security/Commit', 'Total/Commit'];
    const rows = langs.map(l => ({
        cells: [
            cell(l.language), cell(fmt(l.repos), true), cell(fmt(l.commits), true),
            cell(fmtDec(l.bugs_per_commit, 3), true),
            cell(fmtDec(l.smells_per_commit, 3), true),
            cell(fmtDec(l.security_per_commit, 3), true),
            cell(fmtDec(l.total_per_commit, 3), true),
        ]
    }));
    document.getElementById('rq1-by-language-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ2MonthlyToolTable(data) {
    const ts = (data.focused && data.focused.time_series) ? data.focused.time_series : (data.time_series || []);
    if (!ts.length) return;
    const tools = ['copilot', 'claude', 'cursor', 'gemini', 'devin'];
    const toolLabels = { copilot: 'Copilot', claude: 'Claude', cursor: 'Cursor', gemini: 'Gemini', devin: 'Devin' };

    // Table 1: Commits per month
    const commitHeaders = ['Month', ...tools.map(t => toolLabels[t]), 'Total'];
    const commitRows = ts.map(entry => ({
        cells: [
            cell(entry.month),
            ...tools.map(t => cell(fmt(entry['tool_' + t] || 0), true)),
            cell(fmt(entry.commits || 0), true),
        ]
    }));
    const commitFooter = [
        cell('Total', false, 'bold'),
        ...tools.map(t => cell(fmt(ts.reduce((s, e) => s + (e['tool_' + t] || 0), 0)), true)),
        cell(fmt(ts.reduce((s, e) => s + (e.commits || 0), 0)), true),
    ];

    // Table 2: Issues/Commit rate per month
    const rateHeaders = ['Month', ...tools.map(t => toolLabels[t])];
    const rateRows = ts.map(entry => ({
        cells: [
            cell(entry.month),
            ...tools.map(t => {
                const commits = entry['tool_' + t] || 0;
                const issues = entry['issues_' + t] || 0;
                const rate = commits > 0 ? (issues / commits) : 0;
                return cell(commits > 0 ? fmtDec(rate, 2) : '—', true);
            }),
        ]
    }));

    // Table 3: Issues per month
    const issueHeaders = ['Month', ...tools.map(t => toolLabels[t]), 'Total'];
    const issueRows = ts.map(entry => ({
        cells: [
            cell(entry.month),
            ...tools.map(t => cell(fmt(entry['issues_' + t] || 0), true)),
            cell(fmt(entry.issues || 0), true),
        ]
    }));

    const el = document.getElementById('rq2-monthly-tool-table');
    if (!el) return;
    el.innerHTML =
        '<h4 style="margin:0 0 0.5rem;font-size:0.85rem;">Commits Over Time</h4>' +
        buildTableHTML(commitHeaders, commitRows, commitFooter) +
        '<h4 style="margin:1.5rem 0 0.5rem;font-size:0.85rem;">Issues Over Time</h4>' +
        buildTableHTML(issueHeaders, issueRows) +
        '<h4 style="margin:1.5rem 0 0.5rem;font-size:0.85rem;">Issues/Commit Over Time</h4>' +
        buildTableHTML(rateHeaders, rateRows);
}

function renderRQ2ToolTable(data) {
    const byTool = _ftools(data);
    const sorted = Object.entries(byTool)
        .filter(([_, t]) => t.commits >= 10)
        .sort((a, b) => b[1].commits - a[1].commits);

    // Overall table
    const headers1 = ['Coding Tool', 'Commits', 'Files', 'Issues/Commit', 'Issues/File', 'Zero-Issue %'];
    const rows1 = sorted.map(([key, t]) => ({
        cells: [
            cell(toolName(key)),
            cell(fmt(t.commits), true),
            cell(fmt(t.actionable_files || t.files_analyzed || 0), true),
            cell(fmtDec(t.actionable_per_commit || t.issues_per_commit_mean, 2), true),
            cell(fmtDec(t.actionable_per_file || t.issues_per_file, 3), true),
            cell(fmtPct(t.zero_issue_pct), true),
        ]
    }));

    // By family table
    const headers2 = ['Coding Tool', 'Bug/Commit', 'Smell/Commit', 'Security/Commit', 'Bug/File', 'Smell/File', 'Security/File'];
    const rows2 = sorted.map(([key, t]) => ({
        cells: [
            cell(toolName(key)),
            cell(fmtDec(t.bugs_per_commit || 0, 3), true),
            cell(fmtDec(t.smells_per_commit || 0, 3), true),
            cell(fmtDec(t.security_per_commit || 0, 3), true),
            cell(fmtDec(t.bugs_per_file || 0, 4), true),
            cell(fmtDec(t.smells_per_file || 0, 4), true),
            cell(fmtDec(t.security_per_file || 0, 4), true),
        ]
    }));

    // Issue count by family
    const headers3 = ['Coding Tool', 'Total', 'Bugs', 'Code Smells', 'Security', 'Bug %', 'Security %'];
    const rows3 = sorted.map(([key, t]) => {
        const total = t.actionable_issues || 0;
        const bugs = t.bugs || 0;
        const smells = t.smells || 0;
        const sec = t.security_issues || 0;
        return {
            cells: [
                cell(toolName(key)),
                cell(fmt(total), true),
                cell(fmt(bugs), true),
                cell(fmt(smells), true),
                cell(fmt(sec), true),
                cell(fmtPct(total > 0 ? bugs / total * 100 : 0), true),
                cell(fmtPct(total > 0 ? sec / total * 100 : 0), true),
            ]
        };
    });

    document.getElementById('rq2-tool-table').innerHTML =
        '<h4 style="margin:0 0 0.5rem;font-size:0.85rem;">Overall</h4>' +
        buildTableHTML(headers1, rows1) +
        '<h4 style="margin:1.5rem 0 0.5rem;font-size:0.85rem;">Issue Counts by Family</h4>' +
        buildTableHTML(headers3, rows3) +
        '<h4 style="margin:1.5rem 0 0.5rem;font-size:0.85rem;">Rates by Family</h4>' +
        buildTableHTML(headers2, rows2);
}

function renderRQ2RoleToolTable(data) {
    const byTool = _ftools(data);
    const sorted = Object.entries(byTool)
        .filter(([_, t]) => t.commits >= 10 && t.sole_author_commits > 0 && t.coauthor_commits > 0)
        .sort((a, b) => b[1].commits - a[1].commits);

    const headers = ['Coding Tool', 'Sole Commits', 'Sole Issues/Commit', 'Co-Author Commits', 'Co-Author Issues/Commit', 'Difference'];
    const rows = sorted.map(([key, t]) => {
        const soleRate = t.sole_issues_per_commit || 0;
        const coRate = t.co_issues_per_commit || 0;
        const diff = soleRate - coRate;
        const diffCls = diff > 0 ? 'highlight-worst' : diff < 0 ? 'highlight-best' : '';
        return {
            cells: [
                cell(toolName(key)),
                cell(fmt(t.sole_author_commits), true), cell(fmtDec(soleRate), true),
                cell(fmt(t.coauthor_commits), true), cell(fmtDec(coRate), true),
                cell((diff > 0 ? '+' : '') + fmtDec(diff), true, diffCls),
            ]
        };
    });

    document.getElementById('rq2-role-tool-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ2Ranking(data) {
    const ranked = Object.entries(_ftools(data))
        .map(([tool, stats]) => ({
            tool,
            issues_per_commit: stats.issues_per_commit_mean || 0,
            commits: stats.commits || 0,
            repos: stats.repos_with_code || stats.repos || 0,
        }))
        .filter(t => t.commits >= 10)
        .sort((a, b) => a.issues_per_commit - b.issues_per_commit);

    const headers = ['Rank', 'Coding Tool', 'Issues/Commit (mean)', 'Commits', 'Repos'];
    const rows = ranked.map((t, i) => ({
        cells: [
            cell(i + 1, true, i === 0 ? 'highlight-best' : i === ranked.length - 1 ? 'highlight-worst' : ''),
            cell(toolName(t.tool)),
            cell(fmtDec(t.issues_per_commit), true),
            cell(fmt(t.commits), true),
            cell(fmt(t.repos || '—'), true),
        ]
    }));

    document.getElementById('rq2-ranking-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ3SurvivalOverview(data) {
    const s = _fsurv(data).issue_survival || _fsurv(data);
    const headers = ['Metric', 'Value'];
    const rows = [
        { cells: [cell('Total Issues Tracked'), cell(fmt(s.total_tracked), true)] },
        { cells: [cell('Surviving (unfixed at HEAD)'), cell(fmt(s.surviving), true)] },
        { cells: [cell('Fixed'), cell(fmt(s.fixed), true)] },
        { cells: [cell('Survival Rate'), cell(fmtPct(s.survival_rate * 100), true, s.survival_rate > 0.5 ? 'highlight-worst' : 'highlight-best')] },
        { cells: [cell('Fix Rate'), cell(fmtPct((1 - s.survival_rate) * 100), true)] },
    ];

    document.getElementById('rq3-survival-overview').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ3SurvivalFamily(data) {
    const byFamily = _fsurv(data).by_family || {};
    const FAMILY_LABELS = { bug: 'Bug', code_smell: 'Code Smell', security: 'Security' };
    const families = ['bug', 'code_smell', 'security'].filter(f => byFamily[f]);
    const headers = ['Family', 'Total Tracked', 'Surviving', 'Fixed', 'Survival Rate'];
    const rates = families.map(f => byFamily[f].rate || 0);
    const bestRate = Math.min(...rates);
    const worstRate = Math.max(...rates);
    const rows = families.map(f => {
        const s = byFamily[f];
        const fixed = s.fixed ?? (s.total - s.surviving);
        const rate = s.rate || 0;
        const cls = rate === worstRate ? 'highlight-worst' : rate === bestRate ? 'highlight-best' : '';
        return { cells: [
            cell(FAMILY_LABELS[f] || f),
            cell(fmt(s.total), true),
            cell(fmt(s.surviving), true),
            cell(fmt(fixed), true),
            cell(fmtPct(rate * 100), true, cls),
        ]};
    });
    const totalT = families.reduce((a, f) => a + (byFamily[f].total || 0), 0);
    const totalS = families.reduce((a, f) => a + (byFamily[f].surviving || 0), 0);
    const footer = [
        cell('Total', false, 'bold'), cell(fmt(totalT), true),
        cell(fmt(totalS), true), cell(fmt(totalT - totalS), true),
        cell(fmtPct(totalT > 0 ? totalS / totalT * 100 : 0), true),
    ];
    document.getElementById('rq3-survival-family').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderRQ3SurvivalByAge(data) {
    const cohorts = _fsurv(data).survival_by_age || [];
    if (!cohorts.length) {
        document.getElementById('rq3-survival-by-age').innerHTML = '<p style="color:var(--text-muted)">No survival-by-age data available.</p>';
        return;
    }
    const hasFam = !!cohorts[0].by_family;

    // Sub-table 1: Overview with survival rate and per-100-commits
    const h1 = ['Age Cohort', 'Commits', 'Issues', 'Surviving', 'Surv. Rate', 'Surv./100 Commits'];
    const rateCls = (r) => r > 0.4 ? 'highlight-worst' : r < 0.2 ? 'highlight-best' : '';
    const rows1 = cohorts.map(c => ({ cells: [
        cell(c.label),
        cell(fmt(c.commits || 0), true),
        cell(fmt(c.total), true),
        cell(fmt(c.surviving), true),
        cell(fmtPct((c.survival_rate || 0) * 100), true, rateCls(c.survival_rate || 0)),
        cell(fmtDec(c.surviving_per_100_commits || 0), true),
    ]}));
    const gc = cohorts.reduce((s, c) => s + (c.commits || 0), 0);
    const gt = cohorts.reduce((s, c) => s + c.total, 0);
    const gs = cohorts.reduce((s, c) => s + c.surviving, 0);
    const f1 = [cell('All', false, 'bold'), cell(fmt(gc), true), cell(fmt(gt), true), cell(fmt(gs), true),
        cell(fmtPct(gt > 0 ? gs / gt * 100 : 0), true), cell(fmtDec(gc > 0 ? gs / gc * 100 : 0), true)];

    // Sub-table 2: Surviving counts by family
    let html2 = '';
    if (hasFam) {
        const h2 = ['Age Cohort', 'Bug Surv.', 'Smell Surv.', 'Security Surv.', 'Bug/100c', 'Smell/100c', 'Sec/100c'];
        const rows2 = cohorts.map(c => {
            const bf = c.by_family || {};
            const cm = c.commits || 1;
            return { cells: [
                cell(c.label),
                cell(fmt((bf.bug || {}).surviving || 0), true),
                cell(fmt((bf.code_smell || {}).surviving || 0), true),
                cell(fmt((bf.security || {}).surviving || 0), true),
                cell(fmtDec(((bf.bug || {}).surviving_per_100_commits) || 0), true),
                cell(fmtDec(((bf.code_smell || {}).surviving_per_100_commits) || 0), true),
                cell(fmtDec(((bf.security || {}).surviving_per_100_commits) || 0), true),
            ]};
        });
        const bugS = cohorts.reduce((s,c) => s + ((c.by_family||{}).bug||{}).surviving||0, 0);
        const smellS = cohorts.reduce((s,c) => s + ((c.by_family||{}).code_smell||{}).surviving||0, 0);
        const secS = cohorts.reduce((s,c) => s + ((c.by_family||{}).security||{}).surviving||0, 0);
        const f2 = [cell('All', false, 'bold'),
            cell(fmt(bugS), true), cell(fmt(smellS), true), cell(fmt(secS), true),
            cell(fmtDec(gc > 0 ? bugS/gc*100 : 0), true), cell(fmtDec(gc > 0 ? smellS/gc*100 : 0), true), cell(fmtDec(gc > 0 ? secS/gc*100 : 0), true)];
        html2 = '<h4 style="margin:1rem 0 0.3rem;font-size:0.85rem;">Surviving Issues by Family</h4>' + buildTableHTML(h2, rows2, f2);
    }

    document.getElementById('rq3-survival-by-age').innerHTML =
        '<h4 style="margin:0 0 0.3rem;font-size:0.85rem;">Overview</h4>' +
        buildTableHTML(h1, rows1, f1) + html2;
}

function renderRQ3CumulativeDebt(data) {
    const series = _fsurv(data).survival_over_time || [];
    if (!series.length) {
        document.getElementById('rq3-cumulative-debt').innerHTML = '<p style="color:var(--text-muted)">No data available.</p>';
        return;
    }
    const headers = ['Month', 'Introduced', 'Cum. Bug', 'Cum. Smell', 'Cum. Security', 'Cum. Total'];
    const rows = series.map(s => {
        const bf = s.by_family || {};
        return { cells: [
            cell(s.month),
            cell(fmt(s.total), true),
            cell(fmt((bf.bug || {}).cum_surviving || 0), true),
            cell(fmt((bf.code_smell || {}).cum_surviving || 0), true),
            cell(fmt((bf.security || {}).cum_surviving || 0), true),
            cell(fmt(s.cum_surviving), true),
        ]};
    });
    const last = series[series.length - 1];
    const bf = last.by_family || {};
    const footer = [
        cell('Total', false, 'bold'),
        cell(fmt(last.cum_total), true),
        cell(fmt((bf.bug || {}).cum_surviving || 0), true),
        cell(fmt((bf.code_smell || {}).cum_surviving || 0), true),
        cell(fmt((bf.security || {}).cum_surviving || 0), true),
        cell(fmt(last.cum_surviving), true),
    ];
    document.getElementById('rq3-cumulative-debt').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderRQ3SurvivalTool(data) {
    const byTool = _fsurv(data).by_tool || {};
    const sorted = Object.entries(byTool)
        .filter(([_, s]) => (s.total || s.total_tracked || 0) >= 10)
        .sort((a, b) => (a[1].rate || a[1].survival_rate || 0) - (b[1].rate || b[1].survival_rate || 0));

    const headers = ['Coding Tool', 'Total Tracked', 'Surviving', 'Fixed', 'Survival Rate'];
    const rates = sorted.map(([_, s]) => s.rate || s.survival_rate || 0);
    const bestRate = Math.min(...rates);
    const worstRate = Math.max(...rates);

    const rows = sorted.map(([key, s]) => {
        const total = s.total || s.total_tracked || 0;
        const surviving = s.surviving || 0;
        const fixed = s.fixed ?? Math.max(0, total - surviving);
        const rate = s.rate || s.survival_rate || 0;
        const cls = rate === bestRate ? 'highlight-best' : rate === worstRate ? 'highlight-worst' : '';
        return {
            cells: [
                cell(toolName(key)),
                cell(fmt(total), true),
                cell(fmt(surviving), true),
                cell(fmt(fixed), true),
                cell(fmtPct(rate * 100), true, cls),
            ]
        };
    });

    document.getElementById('rq3-survival-tool').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ3LineSurvival(data) {
    const ls = _fsurv(data).line_survival || {};
    const ss = _fsurv(data).semantic_survival || {};

    const headers = ['Metric', 'Line Survival', 'Semantic Survival'];
    const rows = [
        { cells: [cell('Mean'), cell(fmtPct((ls.mean || 0) * 100), true), cell(fmtPct((ss.mean || 0) * 100), true)] },
        { cells: [cell('Median'), cell(fmtPct((ls.median || 0) * 100), true), cell(fmtPct((ss.median || 0) * 100), true)] },
        { cells: [cell('P25'), cell(fmtPct((ls.p25 || 0) * 100), true), cell(fmtPct((ss.p25 || 0) * 100), true)] },
        { cells: [cell('P75'), cell(fmtPct((ls.p75 || 0) * 100), true), cell(fmtPct((ss.p75 || 0) * 100), true)] },
        { cells: [cell('Commits Analyzed'), cell(fmt(ls.count || 0), true), cell(fmt(ss.count || 0), true)] },
    ];

    document.getElementById('rq3-line-survival').innerHTML = buildTableHTML(headers, rows);
}

function renderRQ3FileLifecycle(data) {
    const fl = _ffile(data);
    const total = fl.total_files || 1;

    const headers = ['File Fate', 'Count', '% of Total'];
    const fates = [
        ['Survived (unchanged)', fl.survived],
        ['Modified', fl.modified],
        ['Deleted', fl.deleted],
        ['Had Bug Fixes', fl.had_fixes],
        ['Refactored', fl.refactored],
    ];

    const rows = fates.map(([label, count]) => ({
        cells: [cell(label), cell(fmt(count || 0), true), cell(fmtPct((count || 0) / total * 100), true)]
    }));

    const footer = [cell('Total Files', false, 'bold'), cell(fmt(total), true), cell('100.0%', true)];
    document.getElementById('rq3-file-lifecycle').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderRQ3SurvivingRules(data) {
    const rules = mergeRuleRows(_fsurv(data).top_surviving_rules || [], {
        ruleField: 'rule',
        sortField: 'surviving',
        limit: 15,
    });

    const headers = ['#', 'Rule', 'Surviving', 'Total', 'Survival Rate'];
    const rows = rules.map((r, i) => ({
        cells: [
            cell(i + 1, true),
            cell(r.label),
            cell(fmt(r.surviving || 0), true),
            cell(fmt(r.total || r.total_tracked || 0), true),
            cell(fmtPct(((r.rate ?? r.survival_rate) || 0) * 100), true),
        ]
    }));

    document.getElementById('rq3-surviving-rules').innerHTML = buildTableHTML(headers, rows);
}

function renderFilteringSummary(data) {
    const summary = (_ffilter(data).summary) || {};
    const total = summary.total_issues || 0;
    const headers = ['Bucket', 'Count', '% of Total'];
    const rows = [
        { cells: [cell('Visible by Default'), cell(fmt(summary.visible_by_default || 0), true), cell(fmtPct(summary.visible_rate || 0), true)] },
        { cells: [cell('Low-Signal Hidden'), cell(fmt(summary.low_signal || 0), true), cell(fmtPct(total > 0 ? ((summary.low_signal || 0) / total * 100) : 0), true)] },
        { cells: [cell('Likely False Positive Hidden'), cell(fmt(summary.likely_false_positive || 0), true), cell(fmtPct(total > 0 ? ((summary.likely_false_positive || 0) / total * 100) : 0), true)] },
        { cells: [cell('Filtered Total'), cell(fmt(summary.filtered_total || 0), true), cell(fmtPct(summary.filtered_rate || 0), true)] },
    ];
    const footer = [cell('Total Issues', false, 'bold'), cell(fmt(total), true), cell('100.0%', true)];
    document.getElementById('filtering-summary-table-paper').innerHTML = buildTableHTML(headers, rows, footer);
}

function renderFilteringRules(data) {
    const summary = (_ffilter(data).summary) || {};
    const rowsData = mergeRuleRows(_ffilter(data).filtered_rules || [], {
        sortField: 'count',
        limit: 15,
        totalCount: summary.total_issues || 0,
        filteredTotal: summary.filtered_total || 0,
    });
    const headers = ['#', 'Rule', 'Filtered', '% of Total', '% of Filtered'];
    const rows = rowsData.map((r, i) => ({
        cells: [
            cell(i + 1, true),
            cell(r.label),
            cell(fmt(r.count || 0), true),
            cell(fmtPct(r.share_pct || 0), true),
            cell(fmtPct(r.filtered_share_pct || 0), true),
        ]
    }));
    document.getElementById('filtering-rules-table').innerHTML = buildTableHTML(headers, rows);
}

function renderRuleNormalizationNote(data) {
    const focused = data.focused || {};
    const familyRows = Object.values(focused.top_rules_by_family || {}).map(rows => mergeRuleRows(rows || [], { limit: 20 }));
    const languageRows = Object.values(focused.top_rules_by_language || {}).map(rows => mergeRuleRows(rows || [], { limit: 20 }));
    const overallRows = [mergeRuleRows(_frq1(data).top_rules || [], { limit: 25 })];
    const survivalRows = [mergeRuleRows(_fsurv(data).top_surviving_rules || [], { ruleField: 'rule', sortField: 'surviving', limit: 20 })];
    const filteringRows = [mergeRuleRows(_ffilter(data).filtered_rules || [], { limit: 20 })];
    const notes = collectMergedRuleNotes([...familyRows, ...languageRows, ...overallRows, ...survivalRows, ...filteringRows]);
    const el = document.getElementById('rule-normalization-note');
    if (!el) return;
    if (!notes.length) {
        el.innerHTML = '';
        return;
    }
    el.innerHTML = `
        <div class="table-card">
            <h3>Rule Label Notes</h3>
            <p class="table-caption">Tables on this page use human-readable rule labels. One-to-one labels are plain-English renderings of the original analyzer rule names. The merged labels below combine equivalent raw rules across analyzers or language variants. For the full appendix-style catalog of family membership and raw rule mappings, see <a href="rule-notes.html${datasetQuery()}" data-preserve-dataset="true">Rule Notes</a>.</p>
            <table class="paper-table">
                <tr><th>Displayed Label</th><th>Raw Rule Names / IDs</th></tr>
                ${notes.map(note => `<tr><td>${note.label}</td><td><code>${note.raw_rules.join('</code>, <code>')}</code></td></tr>`).join('')}
            </table>
        </div>`;
}

// ── Main ──

function applyLoadedData(data, { initial = false } = {}) {
    updateDataStatusBanner(data, data._refresh_meta || null);

    if (initial) {
        document.getElementById('loading-msg').style.display = 'none';
        document.getElementById('paper-content').style.display = 'block';
    }

    // Dataset
    renderDatasetStats(data);
    renderDatasetToolTable(data);
    renderDatasetLangTable(data);
    renderMonthlyDistribution(data);

    // RQ1
    renderRQ1Family(data);
    renderRQ1FamilyRules(data);
    renderRQ1LanguageRules(data);
    renderRQ1Rules(data);
    renderRQ1Role(data);
    renderRQ1ByStars(data);
    renderRQ1ByLanguage(data);
    renderRQ2MonthlyToolTable(data);

    // RQ2
    renderRQ2ToolTable(data);
    renderRQ2RoleToolTable(data);
    renderRQ2Ranking(data);

    // RQ3
    renderRQ3SurvivalOverview(data);
    renderRQ3SurvivalFamily(data);
    renderRQ3SurvivalByAge(data);
    renderRQ3CumulativeDebt(data);
    renderRQ3SurvivalTool(data);
    renderRQ3LineSurvival(data);
    renderRQ3FileLifecycle(data);
    renderRQ3SurvivingRules(data);
    renderFilteringSummary(data);
    renderFilteringRules(data);
    renderRuleNormalizationNote(data);
}

function startAutoRefresh() {
    if (_refreshTimer) clearInterval(_refreshTimer);
    _refreshTimer = window.setInterval(async () => {
        if (document.hidden || _refreshInFlight) return;
        _refreshInFlight = true;
        try {
            const refreshed = await loadData();
            if (refreshed) applyLoadedData(refreshed);
        } finally {
            _refreshInFlight = false;
        }
    }, AUTO_REFRESH_MS);
}

async function init() {
    applyDatasetLinks();
    const data = await loadData();
    if (!data) {
        document.getElementById('loading-msg').textContent =
            'Could not load aggregate_summary.json. Run the analysis pipeline first.';
        return;
    }
    applyLoadedData(data, { initial: true });
    startAutoRefresh();

    // Active nav highlighting
    const navLinks = document.querySelectorAll('.nav-link');
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                navLinks.forEach(l => l.classList.remove('active'));
                const target = document.querySelector(`.nav-link[href="#${entry.target.id}"]`);
                if (target) target.classList.add('active');
            }
        });
    }, { threshold: 0.3 });
    document.querySelectorAll('.paper-section').forEach(s => observer.observe(s));

    document.addEventListener('visibilitychange', async () => {
        if (document.hidden || _refreshInFlight) return;
        _refreshInFlight = true;
        try {
            const refreshed = await loadData();
            if (refreshed) applyLoadedData(refreshed);
        } finally {
            _refreshInFlight = false;
        }
    });
}

init();
