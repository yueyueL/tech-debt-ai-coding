function resolveDatasetName(defaultName = 'out') {
    const raw = new URLSearchParams(window.location.search).get('dataset') || defaultName;
    return /^[A-Za-z0-9._-]+$/.test(raw) ? raw : defaultName;
}

const RULE_NOTES_DATASET = resolveDatasetName();
const AUTO_REFRESH_MS = 60000;
let _refreshTimer = null;
let _refreshInFlight = false;
let _liveRefreshSupported = false;

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

function fmt(n) { return typeof n === 'number' ? n.toLocaleString() : (n || '—'); }
function fmtPct(n) { return typeof n === 'number' ? n.toFixed(1) + '%' : '—'; }

function datasetQuery(extra = '') {
    if (RULE_NOTES_DATASET === 'out') return extra ? `?${extra}` : '';
    const datasetParam = `dataset=${encodeURIComponent(RULE_NOTES_DATASET)}`;
    return extra ? `?${extra}&${datasetParam}` : `?${datasetParam}`;
}
function appendDatasetToHref(href) {
    if (!href || href.includes('dataset=')) return href;
    const datasetParam = `dataset=${encodeURIComponent(RULE_NOTES_DATASET)}`;
    return href.includes('?') ? `${href}&${datasetParam}` : `${href}?${datasetParam}`;
}
function applyDatasetLinks() {
    document.querySelectorAll('[data-preserve-dataset="true"]').forEach(anchor => {
        const href = anchor.getAttribute('href');
        if (!href || href.startsWith('#') || RULE_NOTES_DATASET === 'out') return;
        anchor.setAttribute('href', appendDatasetToHref(href));
    });
}

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
    limit = null,
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
                surviving: 0,
                total: 0,
                rate: 0,
            });
        }
        const entry = merged.get(info.key);
        entry.raw_rules.add(rawRule);
        entry.count += Number(row?.[countField] || row?.count || 0);
        entry.surviving += Number(row?.surviving || 0);
        entry.total += Number(row?.total || row?.total_tracked || 0);
    }
    const rowsOut = [...merged.values()].map(entry => ({
        ...entry,
        raw_rules: [...entry.raw_rules].sort(),
        rate: entry.total > 0 ? entry.surviving / entry.total : 0,
    }));
    rowsOut.sort((a, b) => (b[sortField] || 0) - (a[sortField] || 0));
    return limit ? rowsOut.slice(0, limit) : rowsOut;
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
    const candidates = [
        `/results/${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `../../results/${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `../results/${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `results/${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `/${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `../../${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `../${RULE_NOTES_DATASET}/aggregate_summary.json`,
        `${RULE_NOTES_DATASET}/aggregate_summary.json`,
    ];
    for (const path of candidates) {
        try {
            const response = await fetch(path, { cache: 'no-store' });
            if (response.ok) return await response.json();
        } catch (error) {
            /* next */
        }
    }
    return null;
}
async function loadData() {
    const refreshMeta = await refreshAggregateMetadata();
    const data = await loadAggregateFile();
    if (data) data._refresh_meta = refreshMeta;
    return data;
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
    el.textContent = `Dataset: ${RULE_NOTES_DATASET}. Aggregate updated: ${refreshedAt}. ${refreshMode}. Counts may change while ${RULE_NOTES_DATASET}/ is still being written.`;
}

function familyDisplayName(key) {
    return key === 'code_smell' ? 'Code Smell' : key.charAt(0).toUpperCase() + key.slice(1);
}

function renderPolicyStats(data) {
    const focused = data.focused || {};
    const allFamilyRules = focused.all_rules_by_family || focused.top_rules_by_family || {};
    const rawRules = new Set();
    for (const rows of Object.values(allFamilyRules)) {
        for (const row of rows || []) rawRules.add(row.name);
    }
    const mergedConcepts = new Set();
    for (const rule of rawRules) mergedConcepts.add(canonicalRuleInfo(rule).key);
    const securityRules = ((allFamilyRules.security || [])).length;
    document.getElementById('policy-stats').innerHTML = [
        ['Raw actionable rules', rawRules.size],
        ['Merged displayed labels', mergedConcepts.size],
        ['Security raw rule ids', securityRules],
        ['Focused issues', ((focused.totals || {}).actionable_introduced || 0)],
    ].map(([label, value]) => `
        <div class="mini-stat">
            <div class="mini-stat-value">${fmt(value)}</div>
            <div class="mini-stat-label">${label}</div>
        </div>
    `).join('');
}

function renderFamilyDefinitions(data) {
    const focused = data.focused || {};
    const byFamily = focused.by_family || {};
    const topRules = focused.top_rules_by_family || {};
    const descriptions = {
        security: 'Security analyzer findings and vulnerability-style rules.',
        bug: 'Correctness/runtime bug patterns such as undefined references, redeclarations, and unreachable code.',
        code_smell: 'Actionable maintainability issues that are not classified as security or runtime bugs.',
    };
    const headers = ['Family', 'Meaning', 'Issues', 'Repos', 'Commits', 'Representative labels'];
    const rows = ['bug', 'code_smell', 'security'].map(family => {
        const meta = byFamily[family] || { issues: 0, repos: 0, commits: 0 };
        const labels = mergeRuleRows(topRules[family] || [], { limit: 4 }).map(row => row.label).join(', ') || '—';
        return `<tr>
            <td>${familyDisplayName(family)}</td>
            <td>${descriptions[family]}</td>
            <td class="num">${fmt(meta.issues)}</td>
            <td class="num">${fmt(meta.repos)}</td>
            <td class="num">${fmt(meta.commits)}</td>
            <td>${labels}</td>
        </tr>`;
    }).join('');
    document.getElementById('family-definitions-table').innerHTML = `
        <tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>
        ${rows}
    `;
}

function renderFamilyCatalog(data) {
    const focused = data.focused || {};
    const allRules = focused.all_rules_by_family || focused.top_rules_by_family || {};
    const grid = document.getElementById('family-catalog-grid');
    const cards = ['bug', 'code_smell', 'security'].map(family => {
        const merged = mergeRuleRows(allRules[family] || []);
        if (!merged.length) return '';
        return `
            <div class="note-card">
                <h3>${familyDisplayName(family)}</h3>
                <p class="caption">Displayed label, raw analyzer rule names, and current focused-dataset counts.</p>
                <table class="paper-table">
                    <tr><th>Displayed Label</th><th>Raw Rules / IDs</th><th>Count</th></tr>
                    ${merged.map(row => `<tr>
                        <td>${row.label}</td>
                        <td><code>${row.raw_rules.join('</code>, <code>')}</code></td>
                        <td class="num">${fmt(row.count)}</td>
                    </tr>`).join('')}
                </table>
            </div>`;
    }).join('');
    grid.innerHTML = cards;
}

function renderSupplementalCatalog(data) {
    const focused = data.focused || {};
    const filtering = mergeRuleRows((((focused.filtering || {}).filtered_rules) || []), { limit: 20 });
    const survival = mergeRuleRows((((focused.survival || {}).top_surviving_rules) || []), { ruleField: 'rule', sortField: 'surviving', limit: 20 });

    document.getElementById('filtered-labels-table').innerHTML = `
        <tr><th>Displayed Label</th><th>Raw Rules / IDs</th><th>Filtered Count</th></tr>
        ${filtering.map(row => `<tr>
            <td>${row.label}</td>
            <td><code>${row.raw_rules.join('</code>, <code>')}</code></td>
            <td class="num">${fmt(row.count)}</td>
        </tr>`).join('')}
    `;

    document.getElementById('survival-labels-table').innerHTML = `
        <tr><th>Displayed Label</th><th>Raw Rules / IDs</th><th>Surviving</th><th>Total</th></tr>
        ${survival.map(row => `<tr>
            <td>${row.label}</td>
            <td><code>${row.raw_rules.join('</code>, <code>')}</code></td>
            <td class="num">${fmt(row.surviving)}</td>
            <td class="num">${fmt(row.total)}</td>
        </tr>`).join('')}
    `;
}

function applyLoadedData(data, { initial = false } = {}) {
    updateDataStatusBanner(data, data._refresh_meta || null);
    if (initial) {
        document.getElementById('loading-msg').style.display = 'none';
        document.getElementById('content').style.display = 'block';
    }
    renderPolicyStats(data);
    renderFamilyDefinitions(data);
    renderFamilyCatalog(data);
    renderSupplementalCatalog(data);
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
        document.getElementById('loading-msg').textContent = 'Could not load aggregate_summary.json. Rebuild the aggregate first.';
        return;
    }
    applyLoadedData(data, { initial: true });
    startAutoRefresh();

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
    document.querySelectorAll('.notes-section').forEach(s => observer.observe(s));

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
