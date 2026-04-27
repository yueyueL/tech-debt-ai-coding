/**
 * AI Code Quality — Research Overview Dashboard
 * Loads aggregate_summary.json and renders cross-repo visualizations.
 */

// Chart.js defaults
Chart.defaults.color = '#a1a1aa';
Chart.defaults.borderColor = 'rgba(63,63,70,0.3)';
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.font.size = 11;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
Chart.defaults.plugins.tooltip.backgroundColor = '#1f1f23';
Chart.defaults.plugins.tooltip.borderColor = 'rgba(129,140,248,0.3)';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.elements.bar.borderRadius = 4;

const COLORS = {
    primary: '#818cf8', secondary: '#a78bfa', success: '#34d399',
    danger: '#f87171', warning: '#fbbf24', info: '#38bdf8', muted: '#71717a',
};
const TOOL_COLORS = {
    copilot: '#34d399', claude: '#a78bfa', cursor: '#818cf8',
    mend: '#fbbf24', coderabbit: '#38bdf8', devin: '#f97316',
    gemini: '#fb923c', unknown: '#71717a',
};
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
const FOCUSED_AGENTS = ['copilot', 'claude', 'gemini', 'cursor', 'devin'];

let _aggData = null;
const _severityFilter = 'all'; // severity filter removed - always 'all'
let _roleFilter = 'all'; // 'all' | 'sole_author' | 'coauthor'
let _timeRange = 'all'; // 'all', '12m', '6m', '3m'
let _focusedMode = true; // Default: show only top 5 tools
let _refreshTimer = null;
let _refreshInFlight = false;
let _liveRefreshSupported = false;
const AUTO_REFRESH_MS = 60000;

function resolveDatasetName(defaultName = 'out') {
    const raw = new URLSearchParams(window.location.search).get('dataset') || defaultName;
    return /^[A-Za-z0-9._-]+$/.test(raw) ? raw : defaultName;
}

const AGGREGATE_DATASET = resolveDatasetName();

// All chart instances for proper destroy
let _charts = {};

function getToolColor(t) { return TOOL_COLORS[(t || '').toLowerCase()] || COLORS.muted; }
function stat(value, label, cls = '') { return `<div class="stat-box"><div class="stat-box-value ${cls}">${value}</div><div class="stat-box-label">${label}</div></div>`; }
function pct(n, total) { return total > 0 ? (n / total * 100).toFixed(1) : '0.0'; }
function fmtK(n) { return n >= 10000 ? (n / 1000).toFixed(1) + 'K' : n.toLocaleString(); }
function humanizeRuleId(rule) {
    const raw = String(rule || '').trim();
    if (!raw) return 'Unknown rule';
    let base = raw.includes('/') ? raw.split('/').pop() : raw;
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
    if (grouped) return { key: grouped.key, label: grouped.label };
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
} = {}) {
    const merged = new Map();
    for (const row of rows || []) {
        const rawRule = row?.[ruleField] || row?.name || row?.rule || '?';
        const info = canonicalRuleInfo(rawRule, row?.description || '');
        if (!merged.has(info.key)) {
            merged.set(info.key, {
                key: info.key,
                label: info.label,
                count: 0,
                high: 0,
                medium: 0,
                low: 0,
                surviving: 0,
                total: 0,
                rate: 0,
            });
        }
        const entry = merged.get(info.key);
        entry.count += Number(row?.[countField] || row?.count || 0);
        entry.high += Number(row?.high || 0);
        entry.medium += Number(row?.medium || 0);
        entry.low += Number(row?.low || 0);
        entry.surviving += Number(row?.surviving || 0);
        entry.total += Number(row?.total || row?.total_tracked || 0);
    }
    const rowsOut = [...merged.values()].map(entry => ({
        ...entry,
        rate: entry.total > 0 ? entry.surviving / entry.total : 0,
    }));
    rowsOut.sort((a, b) => (b[sortField] || 0) - (a[sortField] || 0));
    return rowsOut.slice(0, limit);
}
function normalizeFamilyData(byFamily) {
    const norm = {};
    for (const [family, raw] of Object.entries(byFamily || {})) {
        if (typeof raw === 'number') {
            norm[family] = { issues: raw, repos: 0, commits: 0 };
        } else {
            norm[family] = {
                issues: raw?.issues || raw?.count || 0,
                repos: raw?.repos || 0,
                commits: raw?.commits || 0,
            };
        }
    }
    return norm;
}
function datasetQuery(extra = '') {
    if (AGGREGATE_DATASET === 'out') return extra ? `?${extra}` : '';
    const datasetParam = `dataset=${encodeURIComponent(AGGREGATE_DATASET)}`;
    return extra ? `?${extra}&${datasetParam}` : `?${datasetParam}`;
}
function appendDatasetToHref(href) {
    if (!href || href.includes('dataset=')) return href;
    const datasetParam = `dataset=${encodeURIComponent(AGGREGATE_DATASET)}`;
    return href.includes('?') ? `${href}&${datasetParam}` : `${href}?${datasetParam}`;
}
function applyDatasetLinks() {
    document.querySelectorAll('[data-preserve-dataset="true"]').forEach(anchor => {
        const href = anchor.getAttribute('href');
        if (!href || href.startsWith('#') || AGGREGATE_DATASET === 'out') return;
        anchor.setAttribute('href', appendDatasetToHref(href));
    });
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
    // Reproduction-package convention: aggregate lives under results/<dataset>/.
    // Legacy top-level <dataset>/ is kept as a fallback for older runs.
    const paths = [
        `/results/${AGGREGATE_DATASET}/aggregate_summary.json`,
        `../../results/${AGGREGATE_DATASET}/aggregate_summary.json`,
        `../results/${AGGREGATE_DATASET}/aggregate_summary.json`,
        `results/${AGGREGATE_DATASET}/aggregate_summary.json`,
        `/${AGGREGATE_DATASET}/aggregate_summary.json`,
        `../../${AGGREGATE_DATASET}/aggregate_summary.json`,
        `../${AGGREGATE_DATASET}/aggregate_summary.json`,
        `${AGGREGATE_DATASET}/aggregate_summary.json`,
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
    el.textContent = `Dataset: ${AGGREGATE_DATASET}. Aggregate updated: ${refreshedAt}. ${refreshMode}. Counts may change while ${AGGREGATE_DATASET}/ is still being written.`;
}

/** Normalize raw survival severity keys (CONVENTION, ERROR, etc.) to high/medium/low */
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

function setFocusedMode(on) {
    _focusedMode = on;
    document.querySelectorAll('[data-focus]').forEach(b => b.classList.toggle('active', on ? b.dataset.focus === 'top5' : b.dataset.focus === 'all'));
    if (_aggData) renderAll(_aggData);
}

/** Get totals respecting focused mode */
function _getTotals(data) {
    if (_focusedMode && data.focused) return data.focused.totals;
    return data.totals;
}
/** Get RQ1 debt types respecting focused mode, using actionable counts */
function _getRQ1(data) {
    if (_focusedMode && data.focused) {
        const ft = data.focused.totals || {};
        return {
            by_severity: ft.actionable_by_severity || data.focused.by_severity,
            by_family: data.focused.by_family || {},
            by_language: data.focused.by_language,
            top_rules: data.focused.top_rules,
            security_total: data.focused.security_total,
        };
    }
    const gt = data.totals || {};
    return {
        by_severity: gt.actionable_by_severity || data.rq1_debt_types.by_severity,
        by_family: data.rq1_debt_types.by_family || {},
        by_language: gt.actionable_by_language || data.rq1_debt_types.by_language,
        top_rules: data.rq1_debt_types.top_rules,
        security_total: data.rq1_debt_types.security_total,
    };
}
/** Get tool comparison data respecting focused mode */
function _getToolData(data) {
    if (_focusedMode && data.focused) return data.focused.by_tool;
    return data.rq2_tool_comparison.by_tool;
}
function _getByRoleData(data) {
    if (_focusedMode && data.focused && data.focused.by_role) return data.focused.by_role;
    return data.by_role || {};
}
function _getSurvivalData(data) {
    if (_focusedMode && data.focused && data.focused.survival) return data.focused.survival;
    return data.rq3_survival;
}
function _getFileLifecycleData(data) {
    if (_focusedMode && data.focused && data.focused.file_lifecycle) return data.focused.file_lifecycle;
    return data.file_lifecycle || {};
}
function _getFilteringData(data) {
    if (_focusedMode && data.focused && data.focused.filtering) return data.focused.filtering;
    return data.false_positive_patterns || {};
}

function _destroyChart(key) { if (_charts[key]) { _charts[key].destroy(); _charts[key] = null; } }

// ── Data Loading ──

async function loadData() {
    const refreshMeta = await refreshAggregateMetadata();
    const data = await loadAggregateFile();
    if (data) {
        data._refresh_meta = refreshMeta;
    }
    return data;
}

// ── Severity Filter ──

function setSeverityFilter(level) { // no-op: severity filter removed
    // _severityFilter = level;
    // disabled === level));
    if (_aggData) renderAll(_aggData);
}

// ── Role Filter ──

function setRoleFilter(role) {
    _roleFilter = role;
    document.querySelectorAll('.role-filter-btn').forEach(b => b.classList.toggle('active', b.dataset.role === role));
    if (_aggData) renderAll(_aggData);
}

/** Get issue count for current severity + role filter (uses actionable counts) */
function _filteredCount(data) {
    const rd = _getRoleData(data);
    if (rd) {
        if (_severityFilter !== 'all') return (rd.by_severity || {})[_severityFilter] || 0;
        return rd.issues;
    }
    const totals = _getTotals(data);
    const sevData = totals.actionable_by_severity || _getRQ1(data).by_severity || {};
    if (_severityFilter !== 'all') return sevData[_severityFilter] || 0;
    return totals.actionable_introduced || totals.issues_introduced;
}

/** Filter rules list by severity */
function _filteredRules(rules) {
    if (_severityFilter === 'all') return rules;
    return rules.filter(r => (r[_severityFilter] || 0) > 0)
        .map(r => ({ ...r, count: r[_severityFilter] || 0 }))
        .sort((a, b) => b.count - a.count);
}

/**
 * Return the role-specific data sub-object, or null if showing all roles.
 * Usage:  const rd = _getRoleData(data);
 *         const sevData = rd ? rd.by_severity : data.rq1_debt_types.by_severity;
 */
function _getRoleData(data) {
    if (_roleFilter === 'all') return null;
    return _getByRoleData(data)[_roleFilter] || null;
}

// ── Time Range ──

function setTimeRange(range) {
    _timeRange = range;
    document.querySelectorAll('.time-range-btn').forEach(b => b.classList.toggle('active', b.dataset.range === range));
    if (_aggData) renderTimeSeries(_aggData);
}

function _getFilteredTimeSeries(data) {
    const rd = _getRoleData(data);
    // Use focused time_series when in focused mode
    const focusedTs = (_focusedMode && data.focused && data.focused.time_series) ? data.focused.time_series : null;
    const ts = focusedTs || ((rd && rd.time_series) ? rd.time_series : (data.time_series || []));
    if (_timeRange === 'all' || ts.length === 0) return ts;
    const now = new Date();
    const months = _timeRange === '12m' ? 12 : _timeRange === '6m' ? 6 : 3;
    const cutoff = new Date(now.getFullYear(), now.getMonth() - months, 1);
    const cutoffStr = cutoff.toISOString().substring(0, 7);
    return ts.filter(t => t.month >= cutoffStr);
}

// ── Rendering ──

// ── Repo Summary ──

function renderRepoSummary(data) {
    const notable = data.notable;
    const allReposRaw = notable.all_repos || [];
    const totalRepos = _getTotals(data).repos_with_code || _getTotals(data).repos;
    const zeroIssues = notable.repos_zero_issues || 0;

    // When role filter is active, recalculate repo counts using role-specific issue fields
    const roleIssueKey = _roleFilter === 'sole_author' ? 'issues_sole_author'
                       : _roleFilter === 'coauthor' ? 'issues_coauthor'
                       : null;
    const allRepos = roleIssueKey
        ? allReposRaw.filter(r => (r[roleIssueKey] || 0) > 0)
        : allReposRaw;
    const withIssues = allRepos.length;
    const withSecurity = allRepos.filter(r => r.issues_security > 0).length;
    const withHigh = allRepos.filter(r => r.issues_high > 0).length;
    const highRate = allRepos.filter(r => r.issues_per_commit > 5).length;

    function repoStat(value, label, cls = '') {
        return `<div class="stat-box"><div class="stat-box-value ${cls}">${value}</div><div class="stat-box-label">${label}</div></div>`;
    }
    document.getElementById('repo-summary-grid').innerHTML = [
        repoStat(fmtK(totalRepos), 'Total Repos'),
        repoStat(fmtK(withIssues), 'Have Issues', 'negative'),
        repoStat(fmtK(roleIssueKey ? totalRepos - withIssues : zeroIssues), 'Zero Issues', 'positive'),
        repoStat(fmtK(withHigh), 'Have HIGH Issues', 'negative'),
        repoStat(fmtK(withSecurity), 'Have Security Issues', 'negative'),
        repoStat(fmtK(highRate), 'High Rate (>5/commit)', 'warning'),
        repoStat(pct(withIssues, totalRepos) + '%', '% Repos w/ Issues'),
        repoStat(pct(withSecurity, withIssues) + '%', '% of w/ Security'),
    ].join('');
}

// ── Repo Browser ──

let _repoFilter = 'all';
let _repoRoleFilter = 'all'; // 'all' | 'sole_author' | 'coauthor'
let _repoStarsMin = 0;   // 0 = no star filter
let _repoSort = { col: 'issues_introduced', dir: -1 };
let _repoPage = 0;
const _repoPageSize = 50;
let _repoFiltered = [];

function _applyRepoFilter(data) {
    const allRepos = (data.notable.all_repos || []);
    const q = (document.getElementById('repo-browser-search')?.value || '').toLowerCase();

    // Include zero-issue repos only for "zero" filter, otherwise exclude them
    let base;
    if (_repoFilter === 'zero') {
        _repoFiltered = [];
        document.getElementById('repo-table-body').innerHTML =
            `<tr><td colspan="12" style="text-align:center;color:var(--text-muted);padding:1.5rem;">
             ${fmtK(data.notable.repos_zero_issues)} repos have zero issues — no detail available (they are excluded from analysis output).
             </td></tr>`;
        document.getElementById('repo-page-info').textContent = '';
        document.getElementById('repo-page-prev').disabled = true;
        document.getElementById('repo-page-next').disabled = true;
        return;
    } else if (_repoFilter === 'security') {
        base = allRepos.filter(r => r.issues_security > 0);
    } else if (_repoFilter === 'high') {
        base = allRepos.filter(r => r.issues_high > 0);
    } else if (_repoFilter === 'high-rate') {
        base = allRepos.filter(r => r.issues_per_commit > 5);
    } else {
        base = allRepos;
    }

    // Star threshold filter (independent of the category filter above)
    if (_repoStarsMin > 0) base = base.filter(r => (r.stars || 0) >= _repoStarsMin);

    // Role filter
    if (_repoRoleFilter === 'sole_author') base = base.filter(r => (r.issues_sole_author || 0) > 0);
    else if (_repoRoleFilter === 'coauthor') base = base.filter(r => (r.issues_coauthor || 0) > 0);

    if (q) base = base.filter(r => r.name.toLowerCase().includes(q));

    // Sort
    const col = _repoSort.col;
    const dir = _repoSort.dir;
    _repoFiltered = [...base].sort((a, b) => {
        const av = a[col] ?? '', bv = b[col] ?? '';
        if (typeof av === 'number') return dir * (av - bv);
        return dir * String(av).localeCompare(String(bv));
    });

    _repoPage = 0;
    _renderRepoPage();
}

function _renderRepoPage() {
    const start = _repoPage * _repoPageSize;
    const page = _repoFiltered.slice(start, start + _repoPageSize);
    const total = _repoFiltered.length;

    if (page.length === 0) {
        document.getElementById('repo-table-body').innerHTML =
            `<tr><td colspan="12" style="text-align:center;color:var(--text-muted);padding:1.5rem;">No repos match the current filter.</td></tr>`;
    } else {
        document.getElementById('repo-table-body').innerHTML = page.map(r => {
            const slug = r.name.replace('/', '_');
            const highCls = r.issues_high > 0 ? 'negative' : '';
            const secCls = r.issues_security > 0 ? 'negative' : '';
            const rateCls = r.issues_per_commit > 5 ? 'negative' : r.issues_per_commit > 2 ? 'warning' : '';
            const stars = r.stars || 0;
            const starsCls = stars >= 10000 ? 'positive' : stars >= 1000 ? '' : 'muted-text';
            const starsStr = stars >= 1000 ? (stars / 1000).toFixed(1) + 'K' : stars > 0 ? String(stars) : '-';
            const ghUrl = r.github_url || `https://github.com/${r.name}`;
            // Role split bar
            const pctSole = r.pct_sole || 0;
            const roleSplitBar = r.issues_introduced > 0
                ? `<div class="role-split-bar" style="width:60px;display:inline-flex;vertical-align:middle;margin-left:4px;" title="Single-Author: ${pctSole}%  Multi-Author: ${100 - pctSole}%">
                    <div class="sole" style="width:${pctSole}%;"></div>
                    <div class="co" style="width:${100 - pctSole}%;"></div>
                   </div>`
                : '';
            return `<tr>
                <td><a class="repo-link" href="${ghUrl}" target="_blank" title="${r.name}">${r.name}</a></td>
                <td class="${starsCls}" style="font-variant-numeric:tabular-nums;">${starsStr}</td>
                <td style="color:var(--text-muted);font-size:0.75rem;">${r.language || '-'}</td>
                <td style="color:${getToolColor(r.tool)};font-weight:600;">${r.tool}</td>
                <td>${r.commits}</td>
                <td class="negative">${fmtK(r.issues_introduced)}</td>
                <td class="${highCls}">${fmtK(r.issues_high)}</td>
                <td class="${secCls}">${r.issues_security > 0 ? fmtK(r.issues_security) : '-'}</td>
                <td class="${rateCls}">${r.issues_per_commit}</td>
                <td class="positive">${r.issues_fixed > 0 ? fmtK(r.issues_fixed) : '-'}</td>
                <td style="white-space:nowrap;font-variant-numeric:tabular-nums;">${pctSole}%${roleSplitBar}</td>
                <td><a class="repo-link" href="dashboard.html${datasetQuery(`repo=${slug}`)}">View →</a></td>
            </tr>`;
        }).join('');
    }

    const totalPages = Math.ceil(total / _repoPageSize);
    document.getElementById('repo-page-info').textContent =
        total > 0 ? `${start + 1}–${Math.min(start + _repoPageSize, total)} of ${fmtK(total)}` : '0 repos';
    document.getElementById('repo-page-prev').disabled = _repoPage === 0;
    document.getElementById('repo-page-next').disabled = _repoPage >= totalPages - 1;

    // Update sort arrows
    document.querySelectorAll('#repo-table th[data-col]').forEach(th => {
        const arrow = th.querySelector('.sort-arrow');
        if (th.dataset.col === _repoSort.col) {
            th.classList.add('sorted');
            arrow.textContent = _repoSort.dir === 1 ? '↑' : '↓';
        } else {
            th.classList.remove('sorted');
            arrow.textContent = '↕';
        }
    });
}

function repoPageChange(delta) {
    const totalPages = Math.ceil(_repoFiltered.length / _repoPageSize);
    _repoPage = Math.max(0, Math.min(_repoPage + delta, totalPages - 1));
    _renderRepoPage();
}

/** Re-render repo browser table (called on every renderAll) */
function renderRepoBrowser(data) {
    _applyRepoFilter(data);
}

/** One-time setup for repo browser event listeners. Call once on init. */
let _repoBrowserInitialized = false;
function _initRepoBrowser(data) {
    if (_repoBrowserInitialized) return;
    _repoBrowserInitialized = true;

    // Category filter buttons (All / Has Security / Has HIGH / High Rate / Zero Issues)
    document.querySelectorAll('.repo-filter-btn[data-rf]').forEach(btn => {
        btn.addEventListener('click', () => {
            _repoFilter = btn.dataset.rf;
            document.querySelectorAll('.repo-filter-btn[data-rf]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _applyRepoFilter(_aggData);
        });
    });

    // Star threshold buttons (≥100★ / ≥1K★ / ≥10K★)
    document.querySelectorAll('.repo-filter-btn[data-stars]').forEach(btn => {
        btn.addEventListener('click', () => {
            const threshold = parseInt(btn.dataset.stars, 10);
            if (_repoStarsMin === threshold) {
                _repoStarsMin = 0;
                btn.classList.remove('active');
            } else {
                _repoStarsMin = threshold;
                document.querySelectorAll('.repo-filter-btn[data-stars]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            }
            _applyRepoFilter(_aggData);
        });
    });

    // Role filter buttons in repo browser
    document.querySelectorAll('.repo-filter-btn[data-role-f]').forEach(btn => {
        btn.addEventListener('click', () => {
            _repoRoleFilter = btn.dataset.roleF;
            document.querySelectorAll('.repo-filter-btn[data-role-f]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            _applyRepoFilter(_aggData);
        });
    });

    // Search
    const searchEl = document.getElementById('repo-browser-search');
    if (searchEl) {
        searchEl.addEventListener('input', () => _applyRepoFilter(_aggData));
    }

    // Sortable column headers
    document.querySelectorAll('#repo-table th[data-col]').forEach(th => {
        th.addEventListener('click', () => {
            const col = th.dataset.col;
            if (_repoSort.col === col) {
                _repoSort.dir *= -1;
            } else {
                _repoSort.col = col;
                _repoSort.dir = col === 'name' || col === 'tool' || col === 'language' ? 1 : -1;
            }
            _applyRepoFilter(_aggData);
        });
    });
}

function renderAll(data) {
    renderGlobalStats(data);
    renderRoleComparisonPanel(data);
    renderRepoSummary(data);
    renderRQ1(data);
    renderRQ2(data);
    renderTimeSeries(data);
    renderRQ3(data);
    renderNotable(data);
    renderRepoBrowser(data);
    renderMethodologyNotes(data);
}

// ── Role Comparison Panel (side-by-side) ──

function renderRoleComparisonPanel(data) {
    const panel = document.getElementById('role-comparison-panel');
    if (!panel) return;
    const br = _getByRoleData(data);
    const sole = br.sole_author;
    const co = br.coauthor;
    if (!sole || !co) { panel.innerHTML = '<p class="gen-info">No role data available.</p>'; return; }

    function row(label, soleVal, coVal, lowerIsBetter = true, unit = '') {
        const sv = typeof soleVal === 'number' ? soleVal : 0;
        const cv = typeof coVal === 'number' ? coVal : 0;
        const soleCls = lowerIsBetter ? (sv <= cv ? 'role-metric-better' : 'role-metric-worse') : (sv >= cv ? 'role-metric-better' : 'role-metric-worse');
        const coCls = lowerIsBetter ? (cv <= sv ? 'role-metric-better' : 'role-metric-worse') : (cv >= sv ? 'role-metric-better' : 'role-metric-worse');
        return { label, soleHtml: `<span class="${soleCls}">${sv}${unit}</span>`, coHtml: `<span class="${coCls}">${cv}${unit}</span>` };
    }

    const metrics = [
        row('Commits', sole.commits, co.commits, false),
        row('Files Analyzed', sole.files_analyzed, co.files_analyzed, false),
        row('Files/Commit', sole.files_per_commit, co.files_per_commit, false),
        row('Issues Introduced', sole.issues, co.issues, true),
        row('Issues/Commit', sole.issues_per_commit, co.issues_per_commit, true),
        row('Issues/File', sole.issues_per_file, co.issues_per_file, true),
        row('HIGH/File', sole.high_per_file, co.high_per_file, true),
        row('Security/File', sole.security_per_file, co.security_per_file, true),
        row('Zero-Issue Commits', sole.zero_issue_pct, co.zero_issue_pct, false, '%'),
        row('Fix Rate', sole.fix_rate, co.fix_rate, false, '%'),
        row('Net Debt', sole.net_debt, co.net_debt, true),
    ];

    function col(title, cls, getVal) {
        return `<div class="role-compare-col ${cls}">
            <h4 style="color:${cls === 'sole' ? 'var(--accent-success)' : '#fb923c'}">${title}</h4>
            ${metrics.map(m => `<div class="role-metric-row"><span class="role-metric-label">${m.label}</span><span class="role-metric-value">${getVal(m)}</span></div>`).join('')}
        </div>`;
    }

    panel.innerHTML = `<div class="role-compare-grid">
        ${col('Single-Author', 'sole', m => m.soleHtml)}
        <div class="role-compare-vs">vs</div>
        ${col('Multi-Author', 'co', m => m.coHtml)}
    </div>
    <div style="margin-top:0.75rem;padding:0.7rem;background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.25);border-radius:6px;font-size:0.8rem;line-height:1.5;">
        <strong style="color:var(--accent-warning);">Simpson's Paradox Warning:</strong>
        The aggregate comparison above is <em>misleading</em>. Multi-author commits appear to have higher Issues/File (${co.issues_per_file} vs ${sole.issues_per_file}),
        but <strong>within the same tool</strong> (e.g., Copilot), the two groups have nearly identical issue density.
        The aggregate difference is driven by <strong>tool composition</strong>: Claude (high iss/file) accounts for a large share of multi-author issues but few single-author commits.
        <strong>The primary driver of issue density is the tool, not the author count.</strong>
    </div>
    <p class="gen-info" style="margin-top:0.4rem;">
        <strong>Single-Author</strong> = only the AI tool is listed as commit author (${sole.commits} commits, avg ${sole.files_per_commit} files/commit).
        <strong>Multi-Author</strong> = multiple authors listed on the commit, including the AI tool (${co.commits} commits, avg ${co.files_per_commit} files/commit).
        These labels reflect Git attribution metadata only — multi-author does not necessarily imply human review of the code.
    </p>`;
}

function renderGlobalStats(data) {
    const t = _getTotals(data);
    const rq1 = _getRQ1(data);
    const fc = _filteredCount(data);
    const sevLabel = '';
    const roleLabel = _roleFilter === 'all' ? '' : (_roleFilter === 'sole_author' ? ' · Single-Author' : ' · Multi-Author');
    const focusLabel = _focusedMode ? ' · Top 5' : '';
    const byRole = _getByRoleData(data);
    const rd = _roleFilter !== 'all' && byRole[_roleFilter] ? byRole[_roleFilter] : null;

    const roleCommits = rd ? rd.commits : t.commits;
    const roleSecurity = rd ? (rd.issues_security || 0) : rq1.security_total;
    let roleFixed;
    // severity filter removed - always use actionable
    {
        roleFixed = rd ? (rd.issues_fixed || 0) : (t.actionable_fixed || t.issues_fixed);
    }
    const rate = roleCommits > 0 ? (fc / roleCommits).toFixed(2) : '0';
    const secPct = pct(roleSecurity, fc);
    const roleIssuesPerFile = rd ? (rd.issues_per_file || 0) : (t.issues_per_file || 0);
    const roleFixRate = roleFixed > 0 && fc > 0
        ? (100 * roleFixed / (fc + roleFixed)).toFixed(1)
        : (rd ? (rd.fix_rate || 0) : (t.fix_rate || 0));
    const repoCount = t.repos_with_code || t.repos;

    document.getElementById('global-stats').innerHTML = [
        stat(fmtK(repoCount), 'Repos' + focusLabel),
        stat(fmtK(roleCommits), 'AI Commits' + roleLabel),
        stat('+' + fmtK(fc), 'Issues' + sevLabel + roleLabel, 'negative'),
        stat('-' + fmtK(roleFixed), 'Fixed' + sevLabel + roleLabel, 'positive'),
        stat(rate, 'Issues/Commit'),
        stat(roleIssuesPerFile.toFixed(2), 'Issues/File', roleIssuesPerFile > 3 ? 'negative' : ''),
        stat(roleFixRate + '%', 'Fix Rate', Number(roleFixRate) > 60 ? 'positive' : 'warning'),
        stat(secPct + '%', 'Security' + roleLabel),
    ].join('');
}

// ── RQ1 ──

function renderRQ1(data) {
    const rq1 = _getRQ1(data);
    const rd = _getRoleData(data);
    // Use role-specific breakdowns when role filter is active
    const sevData = (rd && rd.by_severity) || rq1.by_severity;
    const familyData = normalizeFamilyData(rq1.by_family || {});
    const langData = (rd && rd.by_language) || rq1.by_language;
    const rulesData = (rd && rd.top_rules) || rq1.top_rules || [];
    const familyOrder = ['code_smell', 'bug', 'security'];
    const familyLabels = familyOrder.filter(label => familyData[label]?.issues);
    const familyNames = { code_smell: 'Code Smell', bug: 'Bug', security: 'Security' };

    // Issue Family donut (bug / code_smell / security)
    _destroyChart('sev');
    _charts.sev = new Chart(document.getElementById('chart-severity'), {
        type: 'doughnut',
        data: {
            labels: familyLabels.map(label => familyNames[label] || label),
            datasets: [{
                data: familyLabels.map(label => familyData[label].issues),
                backgroundColor: [COLORS.warning, COLORS.danger, COLORS.info],
            }],
        },
        options: {
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const family = familyLabels[ctx.dataIndex];
                            const bucket = familyData[family] || { issues: 0, repos: 0, commits: 0 };
                            return `${bucket.issues} issues, ${bucket.commits} commits, ${bucket.repos} repos`;
                        },
                    },
                },
            },
        },
    });

    // Family reach bar
    _destroyChart('type');
    _charts.type = new Chart(document.getElementById('chart-type'), {
        type: 'bar',
        data: {
            labels: familyLabels.map(label => familyNames[label] || label),
            datasets: [
                {
                    label: 'Repos',
                    data: familyLabels.map(label => familyData[label].repos || 0),
                    backgroundColor: COLORS.primary + 'bb',
                },
                {
                    label: 'Commits',
                    data: familyLabels.map(label => familyData[label].commits || 0),
                    backgroundColor: COLORS.info + 'bb',
                },
            ],
        },
        options: {
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const family = familyLabels[ctx.dataIndex];
                            const bucket = familyData[family] || { issues: 0, repos: 0, commits: 0 };
                            const metric = ctx.dataset.label || 'Count';
                            return `${metric}: ${ctx.formattedValue} (${bucket.issues} issues)`;
                        },
                    },
                },
            },
        },
    });

    // Language donut
    _destroyChart('lang');
    const langLabels = Object.keys(langData).filter(l => l !== 'other');
    _charts.lang = new Chart(document.getElementById('chart-language'), {
        type: 'doughnut',
        data: { labels: langLabels, datasets: [{ data: langLabels.map(l => langData[l]), backgroundColor: [COLORS.info, COLORS.warning, COLORS.secondary, COLORS.success] }] },
        options: { plugins: { legend: { position: 'bottom' } } },
    });

    // Top rules — THREE COLUMNS: Overall, High, Medium
    const allRules = mergeRuleRows(rulesData, { sortField: 'count', limit: 25 });
    const topOverall = allRules.slice(0, 10);
    const topHigh = mergeRuleRows(rulesData.filter(r => (r.high || 0) > 0), { sortField: 'high', limit: 10 });
    const topMed = mergeRuleRows(rulesData.filter(r => (r.medium || 0) > 0), { sortField: 'medium', limit: 10 });

    function ruleCol(title, rules, field, color) {
        if (rules.length === 0) return `<div class="rule-col"><h4>${title}</h4><p class="gen-info">No data</p></div>`;
        const max = rules[0][field] || rules[0].count || 1;
        return `<div class="rule-col"><h4>${title}</h4><table class="rule-table">
            <tr><th>Rule</th><th>Count</th><th></th></tr>
            ${rules.map(r => {
                const val = r[field] || r.count;
                return `<tr><td>${r.label}</td><td>${fmtK(val)}</td>
                <td><span class="bar-inline" style="width:${Math.max(4, val / max * 80)}px; background:${color};"></span></td></tr>`;
            }).join('')}
        </table></div>`;
    }

    document.getElementById('top-rules-table').innerHTML = `<div class="rule-cols">
        ${ruleCol('Top Overall', topOverall, 'count', COLORS.primary)}
        ${ruleCol('Top Bug Rules', allRules.filter(r => r.high > 0).sort((a,b) => b.high - a.high).slice(0,10), 'high', COLORS.danger)}
        ${ruleCol('Top Code Smell Rules', allRules.filter(r => r.medium > 0).sort((a,b) => b.medium - a.medium).slice(0,10), 'medium', COLORS.warning)}
    </div>`;

    // Charts: Issue rate by stars and by language
    const byStars = (_focusedMode && data.focused) ? data.focused.by_stars || [] : [];
    const byLangBreak = (_focusedMode && data.focused) ? data.focused.by_language_breakdown || [] : [];

    _destroyChart('byStars');
    if (byStars.length > 0 && document.getElementById('chart-by-stars')) {
        _charts.byStars = new Chart(document.getElementById('chart-by-stars'), {
            type: 'bar',
            data: {
                labels: byStars.map(s => s.label),
                datasets: [
                    { label: 'Bug', data: byStars.map(s => s.bugs_per_commit), backgroundColor: COLORS.danger + 'cc' },
                    { label: 'Code Smell', data: byStars.map(s => s.smells_per_commit), backgroundColor: COLORS.warning + 'cc' },
                    { label: 'Security', data: byStars.map(s => s.security_per_commit), backgroundColor: COLORS.info + 'cc' },
                ],
            },
            options: {
                plugins: { legend: { position: 'top' }, title: { display: false } },
                scales: { x: { stacked: false }, y: { title: { display: true, text: 'Issues/Commit', color: '#a1a1aa' } } },
            },
        });
    }

    _destroyChart('byLang');
    if (byLangBreak.length > 0 && document.getElementById('chart-by-language-family')) {
        const topLangs = byLangBreak.filter(l => l.repos >= 10).slice(0, 10);
        _charts.byLang = new Chart(document.getElementById('chart-by-language-family'), {
            type: 'bar',
            data: {
                labels: topLangs.map(l => l.language),
                datasets: [
                    { label: 'Bug', data: topLangs.map(l => l.bugs_per_commit), backgroundColor: COLORS.danger + 'cc' },
                    { label: 'Code Smell', data: topLangs.map(l => l.smells_per_commit), backgroundColor: COLORS.warning + 'cc' },
                    { label: 'Security', data: topLangs.map(l => l.security_per_commit), backgroundColor: COLORS.info + 'cc' },
                ],
            },
            options: {
                plugins: { legend: { position: 'top' }, title: { display: false } },
                scales: { x: { stacked: false }, y: { title: { display: true, text: 'Issues/Commit', color: '#a1a1aa' } } },
            },
        });
    }

    const filtering = _getFilteringData(data);
    const fs = filtering.summary || {};
    const totalIssues = fs.total_issues || 0;
    document.getElementById('filtering-summary-table').innerHTML = `
        <table class="rule-table">
            <tr><th>Bucket</th><th>Count</th><th>Share</th></tr>
            <tr><td>Visible by Default</td><td>${fmtK(fs.visible_by_default || 0)}</td><td>${totalIssues > 0 ? (fs.visible_rate || 0).toFixed(1) : '0.0'}%</td></tr>
            <tr><td>Low-Signal Hidden</td><td>${fmtK(fs.low_signal || 0)}</td><td>${totalIssues > 0 ? (((fs.low_signal || 0) / totalIssues) * 100).toFixed(1) : '0.0'}%</td></tr>
            <tr><td>Likely False Positive Hidden</td><td>${fmtK(fs.likely_false_positive || 0)}</td><td>${totalIssues > 0 ? (((fs.likely_false_positive || 0) / totalIssues) * 100).toFixed(1) : '0.0'}%</td></tr>
            <tr><td><strong>Filtered Total</strong></td><td><strong>${fmtK(fs.filtered_total || 0)}</strong></td><td><strong>${totalIssues > 0 ? (fs.filtered_rate || 0).toFixed(1) : '0.0'}%</strong></td></tr>
        </table>`;
}

// ── RQ2 ──

function renderRQ2(data) {
    const rd = _getRoleData(data);
    // When role filter active, use role-specific per-tool stats
    const toolsFull = _getToolData(data);
    const toolsFiltered = (rd && rd.by_tool) || toolsFull;
    const tools = toolsFiltered;
    const toolNames = Object.keys(tools).filter(t => tools[t].commits >= 5).sort((a, b) => tools[b].commits - tools[a].commits);

    _destroyChart('toolCommits');
    _charts.toolCommits = new Chart(document.getElementById('chart-tool-commits'), {
        type: 'bar',
        data: { labels: toolNames, datasets: [{ label: 'Commits', data: toolNames.map(t => tools[t].commits), backgroundColor: toolNames.map(getToolColor) }] },
        options: { plugins: { legend: { display: false } } },
    });

    _destroyChart('toolRate');
    _charts.toolRate = new Chart(document.getElementById('chart-tool-rate'), {
        type: 'bar',
        data: { labels: toolNames, datasets: [
            { label: 'Issues/Commit', data: toolNames.map(t => tools[t].issues_per_commit_mean), backgroundColor: toolNames.map(t => getToolColor(t) + 'bb') },
        ] },
        options: { plugins: { legend: { position: 'top' } } },
    });

    // Issues/file bar chart (normalized metric)
    _destroyChart('toolIpf');
    if (document.getElementById('chart-tool-ipf')) {
        _charts.toolIpf = new Chart(document.getElementById('chart-tool-ipf'), {
            type: 'bar',
            data: { labels: toolNames, datasets: [{
                label: 'Issues/File',
                data: toolNames.map(t => tools[t].issues_per_file || 0),
                backgroundColor: toolNames.map(t => getToolColor(t) + 'bb'),
            }] },
            options: { plugins: { legend: { display: false } } },
        });
    }

    // Role comparison chart: sole vs co issues/FILE per tool (normalized!)
    _destroyChart('roleComparison');
    const toolsWithRole = toolNames.filter(t =>
        (toolsFull[t]?.sole_issues_per_file || 0) + (toolsFull[t]?.co_issues_per_file || 0) > 0
    );
    if (toolsWithRole.length > 0 && document.getElementById('chart-role-comparison')) {
        _charts.roleComparison = new Chart(document.getElementById('chart-role-comparison'), {
            type: 'bar',
            data: {
                labels: toolsWithRole,
                datasets: [
                    { label: 'Single-Author (issues/file)', data: toolsWithRole.map(t => toolsFull[t]?.sole_issues_per_file || 0), backgroundColor: 'rgba(52,211,153,0.75)' },
                    { label: 'Multi-Author (issues/file)', data: toolsWithRole.map(t => toolsFull[t]?.co_issues_per_file || 0), backgroundColor: 'rgba(251,146,60,0.75)' },
                ],
            },
            options: {
                plugins: {
                    legend: { position: 'top' },
                    subtitle: { display: true, text: 'Issues per file analyzed — normalizes for commit size. Lower = cleaner code.', color: '#71717a', font: { size: 10 } },
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { title: { display: true, text: 'Issues / File', color: '#a1a1aa' } },
                },
            },
        });
    }

    // Table — show role columns only when not already filtered by role
    const showRoleCols = !rd;
    document.getElementById('tool-comparison-table').innerHTML = `
        <table class="rule-table">
            <tr>
                <th>Tool</th><th>Commits</th><th>Issues</th>
                <th title="Average issues per commit">Iss/Commit</th>
                <th title="Average files analyzed per commit">Files/Commit</th>
                <th title="Issues per file analyzed (normalized)">Iss/File</th>
                <th title="% of commits with zero issues">0-Issue %</th>
                ${showRoleCols ? `<th title="% sole author commits">Solo %</th>
                <th title="Issues per file (AI sole author)" style="color:var(--accent-success)">Solo Iss/f</th>
                <th title="Issues per file (AI co-author)" style="color:#fb923c">Co Iss/f</th>` : ''}
            </tr>
            ${toolNames.map(t => {
                const d = tools[t];
                const df = toolsFull[t] || {};
                const ipf = d.issues_per_file ?? (df.issues_per_file ?? '-');
                const fpc = d.files_per_commit ?? (df.files_per_commit ?? '-');
                const zip = d.zero_issue_pct ?? (df.zero_issue_pct ?? '-');
                return `<tr>
                <td><span style="color:${getToolColor(t)};font-weight:600;">${t}</span></td>
                <td>${fmtK(d.commits)}</td><td>${fmtK(d.actionable_issues || d.issues_total)}</td>
                <td>${d.issues_per_commit_mean}</td>
                <td>${fpc}</td>
                <td style="font-weight:600;">${ipf}</td>
                <td>${zip}%</td>
                ${showRoleCols ? `<td style="color:${(df.pct_sole_author || 0) > 70 ? 'var(--accent-success)' : '#fb923c'}">${df.pct_sole_author ?? '-'}%</td>
                <td style="color:var(--accent-success);font-weight:600;">${df.sole_issues_per_file ?? '-'}</td>
                <td style="color:#fb923c;font-weight:600;">${df.co_issues_per_file ?? '-'}</td>` : ''}
            </tr>`; }).join('')}
        </table>`;

    renderFocusedAgentTable(data, tools);
}

function renderFocusedAgentTable(data, toolsData) {
    const el = document.getElementById('focused-agent-table');
    if (!el) return;

    // Repo coverage should use the full analyzed repo base, not only repos with issues.
    const totalScopedRepos = _getTotals(data).repos_with_code || _getTotals(data).repos || 0;
    const globalTools = _getToolData(data);
    const rd = _getRoleData(data);
    const totalScopedCommits = rd ? (rd.commits || 0) : (_getTotals(data).commits || 0);

    const rows = FOCUSED_AGENTS.map(agent => {
        const td = toolsData[agent] || {};
        const reposCovered = globalTools[agent]?.repos || 0;
        const commits = td.commits || 0;
        const coveragePct = totalScopedRepos > 0 ? (reposCovered / totalScopedRepos * 100).toFixed(2) : '0.00';
        const commitPct = totalScopedCommits > 0 ? (commits / totalScopedCommits * 100).toFixed(2) : '0.00';
        return { agent, reposCovered, coveragePct, commits, commitPct };
    });

    const focusedTotalRepos = rows.reduce((s, r) => s + r.reposCovered, 0);
    const focusedRepoShare = totalScopedRepos > 0 ? (focusedTotalRepos / totalScopedRepos * 100).toFixed(2) : '0.00';
    const focusedTotalCommits = rows.reduce((s, r) => s + r.commits, 0);
    const focusedCommitShare = totalScopedCommits > 0 ? (focusedTotalCommits / totalScopedCommits * 100).toFixed(2) : '0.00';

    el.innerHTML = `
        <table class="rule-table">
            <tr>
                <th>Agent</th>
                <th>Repos Covered</th>
                <th>Coverage %</th>
                <th>Commits</th>
                <th>Commit Share %</th>
            </tr>
            ${rows.map(r => `<tr>
                <td style="font-weight:600;color:${getToolColor(r.agent)}">${r.agent}</td>
                <td>${fmtK(r.reposCovered)}</td>
                <td>${r.coveragePct}%</td>
                <td>${fmtK(r.commits)}</td>
                <td>${r.commitPct}%</td>
            </tr>`).join('')}
            <tr>
                <td><strong>Total (Focused 5)</strong></td>
                <td><strong>${fmtK(focusedTotalRepos)}</strong></td>
                <td><strong>${focusedRepoShare}%</strong></td>
                <td><strong>${fmtK(focusedTotalCommits)}</strong></td>
                <td><strong>${focusedCommitShare}%</strong></td>
            </tr>
        </table>
        <p class="gen-info">Coverage base: ${fmtK(totalScopedRepos)} analyzed repos (full dataset). Commit columns ${_roleFilter === 'all' ? 'use all roles' : `follow ${_roleFilter === 'sole_author' ? 'single-author' : 'multi-author'} filter`}.</p>`;
}

// ── Time Series (with tool comparison + range selector) ──

function renderTimeSeries(data) {
    const ts = _getFilteredTimeSeries(data);
    if (ts.length < 2) return;

    const rd = _getRoleData(data);
    const isRoleFiltered = !!rd;

    // Detect which tools are in the time series — filter by focused tools when active
    const focusedToolSet = (_focusedMode && data.focused) ? new Set(data.focused.tools) : null;
    const toolKeys = [];
    const sampleEntry = ts[0] || {};
    if (!isRoleFiltered) {
        for (const key of Object.keys(sampleEntry)) {
            if (key.startsWith('tool_') && ts.some(t => t[key] > 0)) {
                const toolName = key.replace('tool_', '');
                if (!focusedToolSet || focusedToolSet.has(toolName)) {
                    toolKeys.push(key);
                }
            }
        }
    }
    const mainTools = toolKeys
        .map(k => ({ key: k, name: k.replace('tool_', ''), total: ts.reduce((s, t) => s + (t[k] || 0), 0) }))
        .sort((a, b) => b.total - a.total)
        .slice(0, 6);

    const labels = ts.map(t => t.month);

    // Chart 1: Issues (stacked high vs other) + commits line
    _destroyChart('timeline');
    const highIssues = ts.map(t => t.high_issues || 0);
    const otherIssues = ts.map((t, i) => (t.issues || 0) - highIssues[i]);
    _charts.timeline = new Chart(document.getElementById('chart-timeline'), {
        type: 'bar',
        data: {
            labels,
            datasets: [
                { label: 'Other Issues', data: otherIssues, backgroundColor: COLORS.primary + '88', stack: 'issues' },
                { label: 'HIGH Issues', data: highIssues, backgroundColor: COLORS.danger + 'bb', stack: 'issues' },
                { label: 'Commits', data: ts.map(t => t.commits), type: 'line', borderColor: COLORS.success, backgroundColor: 'transparent', borderWidth: 2, pointRadius: 2, yAxisID: 'y1' },
            ],
        },
        options: {
            responsive: true, interaction: { mode: 'index', intersect: false },
            scales: {
                x: { ticks: { maxRotation: 45, font: { size: 9 } } },
                y: { stacked: true, title: { display: true, text: 'Issues', color: '#a1a1aa' } },
                y1: { position: 'right', grid: { drawOnChartArea: false }, title: { display: true, text: 'Commits', color: '#a1a1aa' } },
            },
            plugins: { legend: { position: 'top' } },
        },
    });

    // Chart 2: Tool commits over time
    _destroyChart('toolTimeline');
    const toolCommitDatasets = mainTools.map(t => ({
        label: t.name,
        data: ts.map(row => row[t.key] || 0),
        borderColor: getToolColor(t.name),
        backgroundColor: 'transparent',
        borderWidth: 2,
        pointRadius: 1.5,
        tension: 0.3,
    }));
    _charts.toolTimeline = new Chart(document.getElementById('chart-tool-timeline'), {
        type: 'line',
        data: { labels, datasets: toolCommitDatasets },
        options: {
            responsive: true, interaction: { mode: 'index', intersect: false },
            scales: {
                x: { ticks: { maxRotation: 45, font: { size: 9 } } },
                y: { title: { display: true, text: 'Commits', color: '#a1a1aa' } },
            },
            plugins: { legend: { position: 'top' } },
        },
    });

    // Chart 3: Per-tool issues over time (stacked area)
    _destroyChart('toolIssues');
    const toolIssueDatasets = mainTools.map(t => ({
        label: t.name,
        data: ts.map(row => row[`issues_${t.name}`] || 0),
        borderColor: getToolColor(t.name),
        backgroundColor: getToolColor(t.name) + '33',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
        tension: 0.3,
    }));
    _charts.toolIssues = new Chart(document.getElementById('chart-tool-issues'), {
        type: 'line',
        data: { labels, datasets: toolIssueDatasets },
        options: {
            responsive: true, interaction: { mode: 'index', intersect: false },
            scales: {
                x: { ticks: { maxRotation: 45, font: { size: 9 } } },
                y: { stacked: true, title: { display: true, text: 'Issues Introduced', color: '#a1a1aa' } },
            },
            plugins: { legend: { position: 'top' } },
        },
    });

    // Chart 4: Per-tool issues/commit rate over time (line)
    _destroyChart('toolRateTime');
    const toolRateDatasets = mainTools
        .filter(t => ts.some(row => (row[`rate_${t.name}`] || 0) > 0))
        .map(t => ({
            label: t.name,
            data: ts.map(row => row[`rate_${t.name}`] || 0),
            borderColor: getToolColor(t.name),
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 1.5,
            tension: 0.3,
        }));
    _charts.toolRateTime = new Chart(document.getElementById('chart-tool-rate-time'), {
        type: 'line',
        data: { labels, datasets: toolRateDatasets },
        options: {
            responsive: true, interaction: { mode: 'index', intersect: false },
            scales: {
                x: { ticks: { maxRotation: 45, font: { size: 9 } } },
                y: { title: { display: true, text: 'Issues / Commit', color: '#a1a1aa' } },
            },
            plugins: {
                legend: { position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            const tool = mainTools[ctx.datasetIndex];
                            if (!tool) return ctx.formattedValue;
                            const month = ts[ctx.dataIndex];
                            const commits = month ? (month[tool.key] || 0) : 0;
                            const issues = month ? (month[`issues_${tool.name}`] || 0) : 0;
                            return `${tool.name}: ${ctx.formattedValue} issues/commit (${issues} issues, ${commits} commits)`;
                        }
                    }
                }
            },
        },
    });
}


// ── RQ3 ──

function renderRQ3(data) {
    const rq3 = _getSurvivalData(data);
    const is = rq3.issue_survival || rq3;
    const humanFixRate = is.total_tracked > 0 ? ((is.fixed / is.total_tracked) * 100).toFixed(1) : '0';
    const ls = rq3.line_survival || {};
    const ss = rq3.semantic_survival || {};

    document.getElementById('survival-stats').innerHTML = [
        stat(fmtK(is.total_tracked), 'Issues Tracked'),
        stat(fmtK(is.surviving), 'Still Survive', 'warning'),
        stat(fmtK(is.fixed), 'Fixed', 'positive'),
        stat((is.survival_rate * 100).toFixed(1) + '%', 'Issue Survival Rate', is.survival_rate > 0.5 ? 'negative' : 'warning'),
        stat(humanFixRate + '%', 'Fix Rate', 'positive'),
        stat(((ls.mean || 0) * 100).toFixed(1) + '%', 'Line Survival (mean)'),
        stat(((ss.mean || 0) * 100).toFixed(1) + '%', 'Semantic Survival (mean)'),
    ].join('');

    // Survival by family (bug / code_smell / security)
    _destroyChart('survFamily');
    const byFamily = rq3.by_family || {};
    const families = ['bug', 'code_smell', 'security'].filter(f => byFamily[f]);
    const FAMILY_COLORS = { bug: COLORS.danger, code_smell: COLORS.warning, security: '#c084fc' };
    const FAMILY_LABELS = { bug: 'Bug', code_smell: 'Code Smell', security: 'Security' };
    if (families.length > 0) {
        _charts.survFamily = new Chart(document.getElementById('chart-survival-family'), {
            type: 'bar',
            data: {
                labels: families.map(f => FAMILY_LABELS[f] || f),
                datasets: [
                    { label: 'Surviving', data: families.map(f => byFamily[f].surviving || 0), backgroundColor: COLORS.danger + 'aa' },
                    { label: 'Fixed', data: families.map(f => (byFamily[f].fixed ?? (byFamily[f].total - byFamily[f].surviving)) || 0), backgroundColor: COLORS.success + 'aa' },
                ],
            },
            options: {
                scales: { x: { stacked: true }, y: { stacked: true, title: { display: true, text: 'Issues', color: '#a1a1aa' } } },
                plugins: {
                    legend: { position: 'top' },
                    subtitle: { display: true, text: 'Surviving vs fixed issues by family classification', color: '#71717a', font: { size: 10 } },
                },
            },
        });
    }

    // Code survival: Line + Semantic side by side
    _destroyChart('lineSurv');
    const lineVals = [ls.p25 || 0, ls.median || 0, ls.mean || 0, ls.p75 || 0];
    const semVals = [ss.p25 || 0, ss.median || 0, ss.mean || 0, ss.p75 || 0];
    _charts.lineSurv = new Chart(document.getElementById('chart-line-survival'), {
        type: 'bar',
        data: {
            labels: ['P25', 'Median', 'Mean', 'P75'],
            datasets: [
                { label: 'Line Survival', data: lineVals.map(v => +(v * 100).toFixed(1)), backgroundColor: COLORS.info + 'bb' },
                { label: 'Semantic Survival', data: semVals.map(v => +(v * 100).toFixed(1)), backgroundColor: COLORS.secondary + 'bb' },
            ],
        },
        options: {
            plugins: { legend: { position: 'top' } },
            scales: { y: { max: 100, title: { display: true, text: '%', color: '#a1a1aa' } } },
        },
    });

    // File lifecycle — post-commit fate
    _destroyChart('fileLC');
    const fl = _getFileLifecycleData(data);
    if (fl.total_files > 0) {
        _charts.fileLC = new Chart(document.getElementById('chart-file-lifecycle'), {
            type: 'doughnut',
            data: {
                labels: ['Survived', 'Modified', 'Deleted', 'Had Fixes', 'Refactored'],
                datasets: [{
                    data: [fl.survived, fl.modified, fl.deleted, fl.had_fixes || 0, fl.refactored || 0],
                    backgroundColor: [COLORS.success, COLORS.warning, COLORS.danger, COLORS.info, COLORS.secondary],
                }],
            },
            options: { plugins: { legend: { position: 'bottom' } } },
        });
    }

    // Surviving rules
    const rules = mergeRuleRows(rq3.top_surviving_rules || [], { ruleField: 'rule', sortField: 'surviving', limit: 12 });
    document.getElementById('surviving-rules-table').innerHTML = `
        <table class="rule-table">
            <tr><th>Rule</th><th>Surviving</th><th>Total</th><th>Rate</th></tr>
            ${rules.map(r => `<tr>
                <td>${r.label}</td><td>${fmtK(r.surviving)}</td><td>${fmtK(r.total)}</td>
                <td class="${r.rate > 0.6 ? 'negative' : r.rate > 0.3 ? 'warning' : 'positive'}">${(r.rate * 100).toFixed(1)}%</td>
            </tr>`).join('')}
        </table>`;

    // Survival rate by tool
    _destroyChart('survTool');
    const survByTool = rq3.by_tool || {};
    const survTools = Object.keys(survByTool).filter(t => survByTool[t].total >= 10).sort((a, b) => survByTool[b].total - survByTool[a].total);
    if (survTools.length > 0 && document.getElementById('chart-survival-tool')) {
        const survRates = survTools.map(t => +(survByTool[t].rate * 100).toFixed(1));
        _charts.survTool = new Chart(document.getElementById('chart-survival-tool'), {
            type: 'bar',
            data: {
                labels: survTools,
                datasets: [{ label: 'Survival Rate %', data: survRates, backgroundColor: survTools.map(t => getToolColor(t) + 'bb') }],
            },
            options: {
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                    subtitle: { display: true, text: 'Lower = better remediation. Issues introduced by each tool that still exist at HEAD.', color: '#71717a', font: { size: 10 } },
                },
                scales: { x: { max: 100, title: { display: true, text: 'Survival Rate (%)', color: '#a1a1aa' } } },
            },
        });
    }

    // Cumulative introduced issues over time
    _destroyChart('introOverTime');
    const ts = _focusedMode && data.focused?.time_series ? data.focused.time_series : (data.time_series || []);
    if (ts.length > 0 && document.getElementById('chart-introduced-over-time')) {
        let cumulative = 0;
        const months = ts.map(t => t.month);
        const cumIssues = ts.map(t => { cumulative += (t.issues || 0); return cumulative; });
        const monthlyIssues = ts.map(t => t.issues || 0);
        _charts.introOverTime = new Chart(document.getElementById('chart-introduced-over-time'), {
            type: 'line',
            data: {
                labels: months,
                datasets: [
                    { label: 'Cumulative Issues', data: cumIssues, borderColor: COLORS.danger, backgroundColor: COLORS.danger + '22', fill: true, tension: 0.3 },
                    { label: 'Monthly Issues', data: monthlyIssues, borderColor: COLORS.warning, backgroundColor: COLORS.warning + '44', type: 'bar' },
                ],
            },
            options: {
                plugins: {
                    legend: { position: 'top' },
                    subtitle: { display: true, text: 'Actionable issues introduced by AI tools over time', color: '#71717a', font: { size: 10 } },
                },
                scales: {
                    y: { title: { display: true, text: 'Issues', color: '#a1a1aa' } },
                },
            },
        });
    }

    // Survival rate by introduction month
    _destroyChart('survOverTime');
    const survOT = rq3.survival_over_time || [];
    if (survOT.length > 0 && document.getElementById('chart-survival-over-time')) {
        _charts.survOverTime = new Chart(document.getElementById('chart-survival-over-time'), {
            type: 'line',
            data: {
                labels: survOT.map(s => s.month),
                datasets: [
                    {
                        label: 'All (monthly)',
                        data: survOT.map(s => +(s.monthly_survival_rate * 100).toFixed(1)),
                        borderColor: COLORS.primary,
                        borderWidth: 2,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Bug',
                        data: survOT.map(s => +((s.by_family?.bug?.monthly_rate || 0) * 100).toFixed(1)),
                        borderColor: COLORS.danger,
                        borderWidth: 1.5,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Code Smell',
                        data: survOT.map(s => +((s.by_family?.code_smell?.monthly_rate || 0) * 100).toFixed(1)),
                        borderColor: COLORS.warning,
                        borderWidth: 1.5,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Security',
                        data: survOT.map(s => +((s.by_family?.security?.monthly_rate || 0) * 100).toFixed(1)),
                        borderColor: '#c084fc',
                        borderWidth: 1.5,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Issues Introduced',
                        data: survOT.map(s => s.total),
                        borderColor: COLORS.muted,
                        backgroundColor: COLORS.muted + '33',
                        type: 'bar',
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                plugins: {
                    legend: { position: 'top' },
                    subtitle: { display: true, text: 'Older issues should have lower survival rates (more time to be fixed). Recent issues naturally survive more.', color: '#71717a', font: { size: 10 } },
                },
                scales: {
                    y: { title: { display: true, text: 'Survival Rate (%)', color: '#a1a1aa' }, max: 100 },
                    y1: { position: 'right', title: { display: true, text: 'Issues', color: '#a1a1aa' }, grid: { drawOnChartArea: false } },
                },
            },
        });
    }
}

// ── Methodology Notes ──

function renderMethodologyNotes(data) {
    const el = document.getElementById('methodology-notes');
    if (!el) return;
    const t = _getTotals(data);
    const br = _getByRoleData(data);
    const sole = br.sole_author || {};
    const co = br.coauthor || {};
    el.innerHTML = `
    <h4 style="margin-bottom:0.5rem;color:var(--text-primary);">How Metrics Are Calculated</h4>
    <ul style="padding-left:1.2rem;margin:0;">
        <li><strong>Issues/Commit</strong> = total issues introduced ÷ total commits. Simple but <em>confounded by commit size</em> — larger commits touch more files and naturally trigger more linter findings.</li>
        <li><strong>Issues/File</strong> = total issues introduced ÷ total files analyzed. <em>The fairer comparison</em> — normalizes for commit granularity. Multi-author commits average ${co.files_per_commit || '?'} files vs ${sole.files_per_commit || '?'} for single-author.</li>
        <li><strong>Fix Rate</strong> = issues later fixed ÷ issues introduced. Single-author: ${sole.fix_rate || '?'}%, Multi-author: ${co.fix_rate || '?'}%. Higher single-author fix rate likely reflects smaller, easier-to-remediate changes.</li>
        <li><strong>Zero-Issue %</strong> = commits with 0 issues ÷ total commits. Most AI commits (${sole.zero_issue_pct || '?'}% single-author, ${co.zero_issue_pct || '?'}% multi-author) introduce no linter issues at all.</li>
        <li><strong>Survival Rate</strong> (RQ3) = issues still present in latest code ÷ total tracked issues. Measured via <code>issue_survival.json</code> per repo.</li>
        <li><strong>Bug / Security per File</strong> = bug-family or security-family issues per file analyzed.</li>
        <li><strong>Author Count</strong>: <span style="color:var(--accent-success)">Single-Author</span> = only the AI tool is listed as commit author. <span style="color:#fb923c">Multi-Author</span> = multiple authors listed on the commit (AI tool + other GitHub accounts). This reflects Git attribution metadata only.</li>
    </ul>
    <h4 style="margin:0.8rem 0 0.3rem;color:var(--text-primary);">Key Confounds</h4>
    <ul style="padding-left:1.2rem;margin:0;">
        <li><strong>Commit size</strong>: Multi-author commits touch ${co.files_per_commit || '?'}x more files than single-author (${sole.files_per_commit || '?'}). Always compare Issues/File, not Issues/Commit, when comparing author counts.</li>
        <li><strong>Tool mix</strong>: Different tools have different single/multi ratios (e.g., copilot is 62% single, claude is 89% multi). Per-tool breakdown controls for this.</li>
        <li><strong>Issue families</strong>: Issues are classified by family (bug/code_smell/security) rather than severity, since ESLint configs.all sets everything to "error" making severity meaningless across tools.</li>
        <li><strong>Tainted commits</strong>: ${data._repos_scanned || '?'} repos scanned; shallow-clone boundary commits excluded (files_total > 200, all status 'A').</li>
    </ul>
    <p style="margin-top:0.6rem;font-size:0.75rem;color:var(--text-muted);">Dataset: ${fmtK(t.commits)} commits across ${fmtK(t.repos_with_code || t.repos)} repos, ${fmtK(t.files_analyzed)} files analyzed. Generated ${data._generated_at || '?'}.</p>
    `;
}

// ── Notable ──

function renderNotable(data) {
    const roleIssueKey = _roleFilter === 'sole_author' ? 'issues_sole_author'
                       : _roleFilter === 'coauthor' ? 'issues_coauthor' : null;

    // Filter high-debt commits by role (each entry now has author_role)
    let hd = (data.notable.high_debt_commits || []);
    if (_roleFilter !== 'all') hd = hd.filter(c => c.author_role === _roleFilter);
    hd = hd.sort((a, b) => (b.high || 0) - (a.high || 0) || b.issues - a.issues);
    document.getElementById('high-debt-table').innerHTML = `
        <table class="rule-table">
            <tr><th>Repo</th><th>Commit</th><th>Tool</th><th>HIGH</th><th>Total</th><th>Sec</th></tr>
            ${hd.slice(0, 12).map(c => `<tr>
                <td>${(c.repo || '').split('/').pop()}</td>
                <td><a href="https://github.com/${c.repo}/commit/${c.commit}" target="_blank" class="line-link"><code>${c.commit}</code></a></td>
                <td style="color:${getToolColor(c.tool)}">${c.tool}</td>
                <td class="${c.high > 0 ? 'negative' : ''}">${c.high || 0}</td>
                <td>${fmtK(c.issues)}</td><td>${c.security > 0 ? c.security : '-'}</td>
            </tr>`).join('')}
        </table>`;

    // Top repos — re-sort by role-specific issues when filtered
    let tr = data.notable.top_repos_by_issues || [];
    if (roleIssueKey) {
        tr = (data.notable.all_repos || [])
            .filter(r => (r[roleIssueKey] || 0) > 0)
            .sort((a, b) => (b[roleIssueKey] || 0) - (a[roleIssueKey] || 0));
    }
    const fixedKey = _roleFilter === 'sole_author' ? 'fixed_sole_author'
                   : _roleFilter === 'coauthor' ? 'fixed_coauthor' : 'issues_fixed';
    document.getElementById('top-repos-table').innerHTML = `
        <table class="rule-table">
            <tr><th>Repo</th><th>Commits</th><th>Issues</th><th>Fixed</th></tr>
            ${tr.slice(0, 12).map(r => `<tr>
                <td><a href="dashboard.html${datasetQuery(`repo=${r.name.replace('/', '_')}`)}" class="line-link">${r.name}</a></td>
                <td>${r.commits}</td>
                <td class="negative">${fmtK(roleIssueKey ? (r[roleIssueKey] || 0) : r.issues_introduced)}</td>
                <td class="positive">${fmtK(r[fixedKey] || 0)}</td>
            </tr>`).join('')}
        </table>
        <p class="gen-info" style="margin-top:0.5rem;">${data.notable.repos_zero_issues} repos had zero issues</p>`;
}

// ── Init ──

function applyLoadedData(data, { initial = false } = {}) {
    _aggData = data;
    updateDataStatusBanner(data, data._refresh_meta || null);

    if (initial) {
        document.getElementById('loading-msg').style.display = 'none';
        document.getElementById('overview-content').style.display = 'block';
    }

    renderAll(data);
    if (initial) _initRepoBrowser(data);

    document.getElementById('gen-info').textContent =
        `Generated: ${data._generated_at || '?'} | ${data._repos_scanned} repos in ${data._elapsed_seconds}s`;
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

document.addEventListener('DOMContentLoaded', async () => {
    applyDatasetLinks();
    const data = await loadData();
    if (!data) {
        document.getElementById('loading-msg').textContent = 'No aggregate data found. Run: python3 -m src.reporting.aggregate --out-dir results/out';
        return;
    }
    applyLoadedData(data, { initial: true });
    startAutoRefresh();

    // Sticky nav
    const nav = document.getElementById('top-nav');
    window.addEventListener('scroll', () => nav.classList.toggle('scrolled', window.scrollY > 10), { passive: true });

    // Wire buttons
    // severity filter buttons removed
    document.querySelectorAll('.role-filter-btn').forEach(b => b.addEventListener('click', () => setRoleFilter(b.dataset.role)));
    document.querySelectorAll('.time-range-btn').forEach(b => b.addEventListener('click', () => setTimeRange(b.dataset.range)));
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
});
