/**
 * AI Code Analysis Dashboard — Global State & Severity Helpers
 * Data variables, severity filtering, rule severity mapping, hotspot rendering.
 */

// Data storage
let debtData = [];
let lifecycleData = [];
let destinyData = [];
let deepScanData = {};  // Deep scan results (CodeQL/SonarQube) - repo-wide
let deepScanCommitsData = {};  // Deep scan commit-level results (before/after)
let issueSurvivalData = {};  // Issue survival analysis results
let researchSummary = {};  // Aggregated research summary
let debugData = {};  // Map of commit SHA to debug info
let currentRepoPath = '';  // Current selected repo data path
let availableRepos = [];  // List of available repos
let showLowSeverity = false;  // Default: hide low severity for cleaner view
let commitsDebtChangesOnly = true;  // Default: only show commits with actual debt changes
let dashboardRoleFilter = 'all';  // 'all' | 'sole_author' | 'coauthor'
let repoFilter = '';  // Repo filter query
let repoLoadSeq = 0;  // Monotonic token to avoid race conditions when switching repos

const DASHBOARD_BLOCKED_RULES = new Set([
    'B101',
    'no-console',
    'curly',
    'import-error',
    'no-name-in-module',
]);
const DASHBOARD_TEST_FP_RULES = new Set([
    'node_api_key',
    'node_password',
    'hardcoded_password',
    'hardcoded_password_default',
    'hardcoded_password_funcarg',
    'B105',
    'B106',
    'B107',
    'jwt_exposed',
    'hardcoded_jwt_secret',
]);
const DASHBOARD_SIMULATION_FP_RULES = new Set([
    'node_insecure_random_generator',
    'insecure_random',
]);
const DASHBOARD_DEV_TOOL_FP_RULES = new Set([
    'B404',
    'B108',
]);
const DASHBOARD_LOW_SIGNAL_RULES = new Set([
    'line-too-long',
    'trailing-whitespace',
    'missing-function-docstring',
    'missing-module-docstring',
    'missing-class-docstring',
    'invalid-name',
    'bad-indentation',
    'consider-using-f-string',
    'too-many-arguments',
    'too-many-locals',
    'too-many-positional-arguments',
    'too-few-public-methods',
    'no-else-return',
    'logging-fstring-interpolation',
    'import-outside-toplevel',
    '@typescript-eslint/no-magic-numbers',
    'no-magic-numbers',
    'sort-keys',
    'one-var',
    'id-length',
    '@typescript-eslint/explicit-member-accessibility',
    '@typescript-eslint/explicit-function-return-type',
    '@typescript-eslint/explicit-module-boundary-types',
    '@typescript-eslint/member-ordering',
    '@typescript-eslint/consistent-type-imports',
    '@typescript-eslint/no-explicit-any',
    '@typescript-eslint/no-inferrable-types',
    '@typescript-eslint/init-declarations',
    '@typescript-eslint/class-methods-use-this',
    '@typescript-eslint/method-signature-style',
    '@typescript-eslint/no-non-null-assertion',
    '@typescript-eslint/no-require-imports',
    '@typescript-eslint/prefer-readonly',
    '@typescript-eslint/naming-convention',
    '@typescript-eslint/sort-type-constituents',
    '@typescript-eslint/no-empty-object-type',
    'capitalized-comments',
    'camelcase',
    'class-methods-use-this',
    'consistent-return',
    'curly',
    'default-case',
    'func-names',
    'func-style',
    'guard-for-in',
    'init-declarations',
    'line-comment-position',
    'logical-assignment-operators',
    'max-lines',
    'max-lines-per-function',
    'max-statements',
    'multiline-comment-style',
    'no-bitwise',
    'no-console',
    'no-continue',
    'no-inline-comments',
    'no-negated-condition',
    'no-nested-ternary',
    'no-param-reassign',
    'no-plusplus',
    'no-ternary',
    'no-undefined',
    'no-underscore-dangle',
    'no-use-before-define',
    '@typescript-eslint/no-use-before-define',
    'no-var',
    'no-void',
    'object-shorthand',
    'prefer-arrow-callback',
    'prefer-const',
    'prefer-destructuring',
    'prefer-named-capture-group',
    'prefer-rest-params',
    'prefer-spread',
    'prefer-template',
    'require-await',
    'require-unicode-regexp',
    'sort-imports',
    'sort-vars',
    'strict',
    'vars-on-top',
]);
const TS_NO_UNDEF_AMBIENT_NAMES = new Set([
    '$',
    '_',
    '$derived',
    '$state',
    'AbortSignal',
    'Bun',
    'Byond',
    'CloseEvent',
    'Deno',
    'DOMException',
    'Document',
    'Electron',
    'Hi',
    'Image',
    'Intl',
    'JSX',
    'MessageEvent',
    'MediaQueryList',
    'MediaQueryListEvent',
    'Meteor',
    'MouseEvent',
    'Node',
    'NodeJS',
    'ReadableStream',
    'React',
    'RequestInit',
    'SVGElement',
    'SVGSVGElement',
    'Template',
    'TouchEvent',
    'Window',
    'WebdriverIO',
    'YT',
    'alert',
    'assert',
    'chrome',
    'customElements',
    'define',
    'jQuery',
    'ko',
    'location',
    'postMessage',
    'self',
    'setImmediate',
]);
const TS_NO_UNDEF_AMBIENT_PREFIXES = [
    'Abort',
    'ArrayBuffer',
    'BigInt',
    'Blob',
    'Canvas',
    'CustomEvent',
    'DataView',
    'DOM',
    'Document',
    'Element',
    'Event',
    'File',
    'Float',
    'FormData',
    'HTML',
    'Headers',
    'Image',
    'Intersection',
    'Intl',
    'Keyboard',
    'Map',
    'MediaQuery',
    'Message',
    'Mutation',
    'Node',
    'Observer',
    'Promise',
    'Proxy',
    'React',
    'Readable',
    'Reflect',
    'Request',
    'Resize',
    'Response',
    'Set',
    'SVG',
    'Symbol',
    'Text',
    'Touch',
    'URL',
    'Uint',
    'Weak',
    'Window',
    'Writable',
];

function formatRepoName(name) {
    return (name || '').replace(/_/g, '/');
}

/**
 * Return debtData filtered by the current dashboardRoleFilter.
 * All other functions should call this instead of reading debtData directly
 * when they want to respect the role filter.
 */
function getActiveDebtData() {
    if (dashboardRoleFilter === 'all') return debtData;
    return debtData.filter(c => (c.author_role || 'unknown') === dashboardRoleFilter);
}

/**
 * Set the author role filter for the per-repo dashboard and re-render.
 */
function setDashboardRoleFilter(role) {
    dashboardRoleFilter = role;
    document.querySelectorAll('.role-filter-dash-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.drole === role)
    );
    renderSummaryCards();
    renderCharts();
    renderTables();
    console.log(`[Dashboard] Role filter: ${role}`);
}

function getFilteredRepos() {
    const query = (repoFilter || '').trim().toLowerCase();
    if (!query) return availableRepos.slice();
    return availableRepos.filter(r => r.displayNameLower.includes(query));
}

/**
 * Toggle display of low severity issues (LOW, INFO, STYLE)
 */
function toggleLowSeverity(show) {
    showLowSeverity = show;
    // Re-render components that show issues
    renderSummaryCards();
    renderCharts();
    renderTables();
    renderEvolutionTimeline();
    // If the commit detail modal is currently open, re-render its contents
    if (_currentModalCommit) {
        const modal = document.getElementById('commit-modal');
        if (modal && modal.style.display === 'flex') {
            showCommitDetails(_currentModalCommit);
        }
    }
    console.log(`[Dashboard] Low severity filter: ${show ? 'showing' : 'hiding'} low severity issues`);
}

/**
 * Toggle commit table filter: only show commits with debt changes (+added or -fixed).
 * Uses getCommitIssueCounts so it respects the low-severity toggle.
 */
function toggleCommitsDebtOnly(show) {
    commitsDebtChangesOnly = !!show;
    renderCommitsTable();
    console.log(`[Dashboard] Commit table debt-change filter: ${commitsDebtChangesOnly ? 'ON' : 'OFF'}`);
}

/**
 * Filter issues based on severity setting
 */
function filterBySeverity(issues, filePath = '') {
    if (showLowSeverity || !issues) return issues;

    return issues.filter(issue => !isIssueLowSeverity({ ...issue, file_path: issue?.file_path || filePath }));
}

function isIssueLowSeverity(issue) {
    const severity = (issue?.severity || '').toString().toLowerCase();
    if (issue?._is_low_severity === true) return true;
    if (isHeuristicLowSignalIssue(issue)) return true;
    return ['low', 'info', 'style', 'convention', 'refactor', 'minor'].includes(severity);
}

function extractNoUndefIdentifier(issue) {
    const message = (issue?.message || '').toString();
    const match = message.match(/^'([^']+)' is not defined\.$/);
    return match ? match[1] : '';
}

function isLikelyTypeScriptNoUndefArtifact(issue) {
    if (getIssueRule(issue) !== 'no-undef') return false;
    const normalizedPath = (issue?.file_path || '').replace(/\\/g, '/').toLowerCase();
    if (
        !normalizedPath.endsWith('.js') &&
        !normalizedPath.endsWith('.jsx') &&
        !normalizedPath.endsWith('.ts') &&
        !normalizedPath.endsWith('.tsx') &&
        !normalizedPath.endsWith('.d.ts')
    ) {
        return false;
    }
    if (normalizedPath.endsWith('.d.ts')) return true;

    const ident = extractNoUndefIdentifier(issue);
    if (!ident) return false;
    if (TS_NO_UNDEF_AMBIENT_NAMES.has(ident)) return true;
    return TS_NO_UNDEF_AMBIENT_PREFIXES.some(prefix => ident.startsWith(prefix));
}

function isHeuristicLowSignalIssue(issue) {
    const rule = getIssueRule(issue);
    if (!rule) return false;
    if (DASHBOARD_LOW_SIGNAL_RULES.has(rule)) return true;

    const message = (issue?.message || '').toString();
    if (rule === 'no-redeclare' && message.includes('built-in global variable')) return true;
    if (rule === '@typescript-eslint/no-unused-vars' && message.includes('only used as a type')) return true;
    if (isLikelyTypeScriptNoUndefArtifact(issue)) return true;
    return false;
}

function inferIssueFilterContext(filePath) {
    const normalized = (filePath || '').replace(/\\/g, '/').toLowerCase();
    return {
        is_test: /(^|\/)(tests?|__tests__|spec|fixtures?|mocks?|testdata|testing)(\/|$)|\.test\.[jt]sx?$|\.spec\.[jt]sx?$|(^|\/)conftest\.py$/.test(normalized),
        is_simulation: /\b(simulation|simulator|simulate|mock|mocked|mocking|stub|stubbed|fake|faked|quantum)\b/.test(normalized),
        is_dev: /(^|\/)(scripts?|tools?|cli|bin)(\/|$)|(^|\/)__main__\.py$|(^|\/)serve\.[jt]s$|dev[-_]?server\.[jt]sx?$/.test(normalized),
    };
}

let _survivalIssueLookupCache = null;

function getRawIssueRule(issue) {
    return issue?.rule_id || issue?.rule || issue?.symbol || issue?.type || '';
}

function getSurvivalLookupKey(commitSha, filePath, issue = {}) {
    const lineRaw = issue?.line ?? 0;
    const line = Number.isFinite(Number(lineRaw)) ? Number(lineRaw) : 0;
    const type = (issue?.type || issue?.detected_by || '').toString();
    const message = (issue?.message || '').toString();
    const severity = (issue?.severity || '').toString();
    return [commitSha || '', filePath || '', line, type, message, severity].join('::');
}

function getSurvivalIssueLookup() {
    if (_survivalIssueLookupCache) return _survivalIssueLookupCache;

    const lookup = new Map();
    debtData.forEach(commit => {
        const commitSha = commit.commit_hash || '';
        (commit.files || []).forEach(file => {
            const filePath = file.file_path || '';
            const context = file.issue_filter_context_after || null;
            (file.issues_added || []).forEach(issue => {
                const key = getSurvivalLookupKey(commitSha, filePath, issue);
                if (!lookup.has(key)) {
                    lookup.set(key, {
                        ...issue,
                        file_path: issue.file_path || filePath,
                        filter_context: issue.filter_context || context,
                    });
                }
            });
        });
    });

    _survivalIssueLookupCache = lookup;
    return lookup;
}

function hydrateSurvivalIssue(issue) {
    if (!issue) return {};

    const hydrated = { ...issue };
    const lookup = getSurvivalIssueLookup();
    const key = getSurvivalLookupKey(issue.commit_sha || '', issue.file_path || '', issue);
    const matched = lookup.get(key);
    if (!matched) return hydrated;

    const recoveredRule = matched.rule || matched.symbol || matched.rule_id || '';
    const currentRule = getRawIssueRule(hydrated);
    if ((!currentRule || currentRule === hydrated.type) && recoveredRule) {
        hydrated.rule_id = recoveredRule;
    }
    ['rule', 'symbol', '_is_low_severity', 'filter_context', 'detected_by', 'category'].forEach(field => {
        if (matched[field] !== undefined) hydrated[field] = matched[field];
    });
    if (!hydrated.file_path && matched.file_path) hydrated.file_path = matched.file_path;
    return hydrated;
}

function getIssueRule(issue) {
    if (issue?.commit_sha) {
        return getRawIssueRule(hydrateSurvivalIssue(issue));
    }
    return getRawIssueRule(issue);
}

function getIssueFilterContext(issue = null, file = null, phase = 'after') {
    const sourceIssue = issue?.commit_sha ? hydrateSurvivalIssue(issue) : issue;
    const issueContext = sourceIssue?.filter_context;
    if (issueContext && typeof issueContext === 'object') return issueContext;

    const fileContext = phase === 'before'
        ? file?.issue_filter_context_before
        : file?.issue_filter_context_after;
    if (fileContext && typeof fileContext === 'object') return fileContext;

    return inferIssueFilterContext(file?.file_path || sourceIssue?.file_path || '');
}

function isBlockedIssue(issue, context = {}) {
    const rule = getIssueRule(issue);
    if (!rule) return false;
    if (DASHBOARD_BLOCKED_RULES.has(rule)) return true;
    if (context.is_test && DASHBOARD_TEST_FP_RULES.has(rule)) return true;
    if (context.is_simulation && DASHBOARD_SIMULATION_FP_RULES.has(rule)) return true;
    if (context.is_dev && DASHBOARD_DEV_TOOL_FP_RULES.has(rule)) return true;
    return false;
}

function filterBlockedIssues(issues, context = {}) {
    if (!issues) return [];
    return issues.filter(issue => !isBlockedIssue(issue, context));
}

function getVisibleIssues(issues, context = {}, filePath = '') {
    return filterBySeverity(filterBlockedIssues(issues, context), filePath) || [];
}

function getVisibleFileIssues(file, issueKey = 'issues_added') {
    const phase = issueKey === 'issues_resolved' ? 'before' : 'after';
    return getVisibleIssues(
        file?.[issueKey] || [],
        getIssueFilterContext(null, file, phase),
        file?.file_path || '',
    );
}

function getFilteredSurvivalEntries(options = {}) {
    const includeLowSeverity = options.includeLowSeverity ?? showLowSeverity;
    const entries = (issueSurvivalData && issueSurvivalData.issues) || [];

    return entries.filter(entry => {
        const original = hydrateSurvivalIssue(entry.original || {});
        const visibleAfterBlocked = filterBlockedIssues(
            [original],
            getIssueFilterContext(original),
        ).length > 0;
        if (!visibleAfterBlocked) return false;
        if (includeLowSeverity) return true;
        return !isIssueLowSeverity(original);
    });
}

function summarizeFilteredIssueSurvival(options = {}) {
    const entries = getFilteredSurvivalEntries(options);
    const bySeverity = {};
    const byRule = {};
    let survivingIssues = 0;

    entries.forEach(entry => {
        const original = hydrateSurvivalIssue(entry.original || {});
        const severity = (original.severity || 'UNKNOWN').toString().toUpperCase();
        const rule = getIssueRule(original) || 'unknown';
        const survived = !!entry.survived;

        bySeverity[severity] = bySeverity[severity] || { total: 0, surviving: 0, rate: 0 };
        bySeverity[severity].total += 1;
        if (survived) {
            bySeverity[severity].surviving += 1;
            survivingIssues += 1;
        }

        byRule[rule] = byRule[rule] || { total: 0, surviving: 0, rate: 0 };
        byRule[rule].total += 1;
        if (survived) byRule[rule].surviving += 1;
    });

    Object.values(bySeverity).forEach(data => {
        data.rate = data.total > 0 ? data.surviving / data.total : 0;
    });
    Object.values(byRule).forEach(data => {
        data.rate = data.total > 0 ? data.surviving / data.total : 0;
    });

    return {
        totalIssues: entries.length,
        survivingIssues,
        fixedIssues: entries.length - survivingIssues,
        bySeverity,
        byRule,
        entries,
    };
}

/**
 * Get issue counts for a single commit, respecting the low-severity filter.
 */
function getCommitIssueCounts(commit) {
    let introduced = 0;
    let fixed = 0;
    (commit.files || []).forEach(file => {
        const added = getVisibleFileIssues(file, 'issues_added');
        const resolved = getVisibleFileIssues(file, 'issues_resolved');
        introduced += added.length;
        fixed += resolved.length;
    });
    return { introduced, fixed };
}

function normalizeSeverity(issue) {
    const issueType = (issue.type || issue.detected_by || '').toString().toLowerCase();
    const sev = (issue.severity || '').toString().trim().toLowerCase();

    if (issueType === 'pylint') {
        if (sev === 'fatal' || sev === 'error') return 'high';
        if (sev === 'warning') return 'medium';
        if (sev === 'refactor' || sev === 'convention') return 'low';
        return 'low';
    }

    if (issueType === 'eslint') {
        if (sev === 'error') return 'high';
        if (sev === 'warning') return 'medium';
        return 'medium';
    }

    if (['high', 'error', 'critical', 'blocker', 'fatal'].includes(sev)) return 'high';
    if (['medium', 'warning', 'major'].includes(sev)) return 'medium';
    if (['low', 'info', 'minor', 'style', 'convention', 'refactor'].includes(sev)) return 'low';

    return 'medium';
}

/**
 * Check whether a severity category name counts as "low severity".
 * Used to filter pre-aggregated by_severity breakdowns in Issue Survival
 * and Deep Scan sections when the "Show Low Severity" toggle is off.
 */
function isLowSeverityCategory(severity) {
    const s = (severity || '').toString().toLowerCase();
    return ['low', 'info', 'style', 'convention', 'refactor', 'minor'].includes(s);
}

/**
 * Build a mapping from rule name to normalized severity using the individual
 * issues stored in issueSurvivalData.issues[].original.  Falls back to a
 * hard-coded list of known pylint convention/refactor rules.
 */
let _ruleSeverityCache = null;

function getRuleSeverityMap() {
    if (_ruleSeverityCache) return _ruleSeverityCache;
    const map = {};

    // 1. Build from issue-level data if available
    const issues = getFilteredSurvivalEntries({ includeLowSeverity: true });
    issues.forEach(entry => {
        const orig = hydrateSurvivalIssue(entry.original || entry);
        const rule = getIssueRule(orig);
        if (!rule) return;
        const sev = (orig.severity || '').toString().toLowerCase();
        const isLow = isIssueLowSeverity(orig) || isLowSeverityCategory(sev);
        // Once a rule is marked low, keep it that way
        if (isLow) {
            map[rule] = 'low';
        } else if (!map[rule]) {
            map[rule] = sev || 'medium';
        }
    });

    // 2. Known low-signal rules (fallback if issues array is incomplete or stale)
    DASHBOARD_LOW_SIGNAL_RULES.forEach(r => {
        if (!map[r]) map[r] = 'low';
    });

    _ruleSeverityCache = map;
    return map;
}

/** Reset the rule severity cache (call when repo data changes) */
function resetRuleSeverityCache() {
    _ruleSeverityCache = null;
    _survivalIssueLookupCache = null;
}

/**
 * Check if a specific rule name should be considered low severity.
 */
function isLowSeverityRule(ruleName) {
    const map = getRuleSeverityMap();
    const mapped = map[ruleName];
    if (mapped) return isLowSeverityCategory(mapped);
    return false;
}

// Track the currently-displayed modal commit so we can re-render on filter toggle
let _currentModalCommit = null;

function renderHighSeverityHotspots() {
    const section = document.getElementById('high-sev-section');
    const commitsEl = document.getElementById('high-sev-commits');
    const filesEl = document.getElementById('high-sev-files');
    if (!section || !commitsEl || !filesEl) return;

    const commitStats = [];
    const fileStats = new Map();

    getActiveDebtData().forEach((commit, idx) => {
        let highCount = 0;
        let example = null;
        (commit.files || []).forEach(file => {
            const issues = getVisibleFileIssues(file, 'issues_added');
            issues.forEach(issue => {
                if (normalizeSeverity(issue) !== 'high') return;
                highCount += 1;
                const key = file.file_path || 'unknown';
                const current = fileStats.get(key) || { file: key, count: 0, commit };
                current.count += 1;
                fileStats.set(key, current);
                if (!example) {
                    example = { file: key, rule: issue.symbol || issue.rule || issue.rule_id || 'unknown' };
                }
            });
        });
        if (highCount > 0) {
            commitStats.push({
                index: idx,
                commit,
                sha: (commit.commit_hash || '').substring(0, 8),
                tool: commit.ai_tool || 'unknown',
                count: highCount,
                example
            });
        }
    });

    const topCommits = commitStats.sort((a, b) => b.count - a.count).slice(0, 8);
    const topFiles = Array.from(fileStats.values()).sort((a, b) => b.count - a.count).slice(0, 8);

    if (topCommits.length === 0 && topFiles.length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';

    commitsEl.innerHTML = topCommits.length === 0
        ? '<p class="no-issues">No high severity issues detected.</p>'
        : topCommits.map(c => `
            <div class="hotspot-item" data-index="${c.index}">
                <div>
                    <div><code>${c.sha}</code> <span class="hotspot-meta">${c.tool}</span></div>
                    ${c.example ? `<div class="hotspot-meta">${c.example.file} • ${c.example.rule}</div>` : ''}
                </div>
                <div class="hotspot-count">+${c.count}</div>
            </div>
        `).join('');

    filesEl.innerHTML = topFiles.length === 0
        ? '<p class="no-issues">No high severity files detected.</p>'
        : topFiles.map(f => `
            <div class="hotspot-item">
                <div>
                    <div><code>${f.file}</code></div>
                    <div class="hotspot-meta">commit ${f.commit?.commit_hash?.substring(0, 8) || '-'}</div>
                </div>
                <div class="hotspot-count">+${f.count}</div>
            </div>
        `).join('');

    // Wire click handlers using the commit object from topCommits
    commitsEl.querySelectorAll('.hotspot-item').forEach((el, i) => {
        if (i >= topCommits.length) return;
        el.addEventListener('click', () => showCommitDetails(topCommits[i].commit));
    });
}

/**
 * Get filtered issue counts from debt data
 */
function getFilteredIssueCounts() {
    let introduced = 0;
    let fixed = 0;

    for (const commit of getActiveDebtData()) {
        for (const file of (commit.files || [])) {
            const addedIssues = getVisibleFileIssues(file, 'issues_added');
            const resolvedIssues = getVisibleFileIssues(file, 'issues_resolved');
            introduced += addedIssues.length;
            fixed += resolvedIssues.length;
        }
    }

    return { introduced, fixed };
}

// Chart instances for proper destruction on repo switch
let debtChartInstance = null;
let toolChartInstance = null;
let valuationChartInstance = null;
