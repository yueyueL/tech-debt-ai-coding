/**
 * AI Code Analysis Dashboard — Modals & CSV Export
 * Commit detail modal, issue rendering, CSV export.
 */

/**
 * Modal handling
 */
function setupModal() {
    const modal = document.getElementById('commit-modal');
    const fileModal = document.getElementById('file-modal');
    const closeBtn = modal.querySelector('.close-btn');

    const closeCommitModal = () => {
        modal.style.display = 'none';
        _currentModalCommit = null;
    };

    closeBtn.onclick = closeCommitModal;
    window.onclick = (e) => {
        if (e.target === modal) closeCommitModal();
        if (e.target === fileModal) fileModal.style.display = 'none';
    };
}

/**
 * Severity ordering for sorting (higher = more severe = shown first)
 */
const _SEVERITY_ORDER = {
    'fatal': 5, 'critical': 5, 'blocker': 5,
    'error': 4, 'high': 4,
    'warning': 3, 'medium': 3, 'major': 3,
    'convention': 2, 'refactor': 2, 'low': 2, 'minor': 2,
    'info': 1, 'style': 1,
};

function _sevOrder(sev) {
    return _SEVERITY_ORDER[(sev || '').toString().toLowerCase()] || 0;
}

/**
 * Get severity color class and border color for an issue
 */
function _sevStyle(sev) {
    const s = (sev || '').toString().toLowerCase();
    if (['fatal', 'critical', 'blocker', 'error', 'high'].includes(s)) {
        return { cls: 'sev-high', border: 'var(--accent-danger)', bg: 'var(--accent-danger-dim)', label: 'HIGH' };
    }
    if (['warning', 'medium', 'major'].includes(s)) {
        return { cls: 'sev-medium', border: 'var(--accent-warning)', bg: 'var(--accent-warning-dim)', label: 'MED' };
    }
    if (['convention', 'refactor', 'low', 'minor', 'info', 'style'].includes(s)) {
        return { cls: 'sev-low', border: 'var(--text-muted)', bg: 'rgba(113,113,122,0.15)', label: 'LOW' };
    }
    return { cls: 'sev-medium', border: 'var(--accent-warning)', bg: 'var(--accent-warning-dim)', label: 'MED' };
}

/**
 * Get type badge style
 */
function _typeStyle(type) {
    const t = (type || '').toLowerCase();
    if (t === 'security' || t === 'bandit' || t === 'semgrep') {
        return { bg: 'rgba(248,113,113,0.2)', color: 'var(--accent-danger)', label: t === 'bandit' ? 'SECURITY' : t.toUpperCase() };
    }
    if (t === 'pylint') {
        return { bg: 'rgba(56,189,248,0.2)', color: 'var(--accent-info)', label: 'PYLINT' };
    }
    if (t === 'eslint') {
        return { bg: 'rgba(251,191,36,0.2)', color: 'var(--accent-warning)', label: 'ESLINT' };
    }
    return { bg: 'rgba(167,139,250,0.2)', color: 'var(--accent-secondary)', label: type.toUpperCase() };
}

function showCommitDetails(commit) {
    _currentModalCommit = commit;  // Track for re-render on filter toggle
    const modal = document.getElementById('commit-modal');
    const sha = commit.commit_hash?.substring(0, 12);
    const fullSha = commit.commit_hash;
    const repo = commit.repo || '';

    // Set header info — commit SHA is a clickable link to GitHub
    const commitUrl = repo && fullSha ? `https://github.com/${repo}/commit/${fullSha}` : '';
    const repoUrl = repo ? `https://github.com/${repo}` : '';
    document.getElementById('modal-commit-info').innerHTML = `
        <strong>Commit:</strong> ${commitUrl
            ? `<a href="${commitUrl}" target="_blank" class="line-link"><code>${sha}</code></a>`
            : `<code>${sha}</code>`} | 
        <strong>Repo:</strong> ${repoUrl
            ? `<a href="${repoUrl}" target="_blank" class="line-link">${repo}</a>`
            : repo} | 
        <strong>AI Tool:</strong> ${commit.ai_tool || 'unknown'}
    `;

    // Collect issues from commit.files - use detailed issues if available
    let allIssuesAdded = [];
    let allIssuesResolved = [];
    let filesChanged = [];

    const files = commit.files || [];
    files.forEach(file => {
        const delta = file.delta || {};

        // Use detailed issues when available, and apply dashboard filtering later.
        const detailedAdded = file.issues_added || [];
        const detailedResolved = file.issues_resolved || [];
        const filteredAdded = getVisibleFileIssues(file, 'issues_added');
        const filteredResolved = getVisibleFileIssues(file, 'issues_resolved');
        const hasDetailed = detailedAdded.length > 0 || detailedResolved.length > 0;

        const added = hasDetailed ? filteredAdded.length : (delta.issues_introduced || 0);
        const resolved = hasDetailed ? filteredResolved.length : (delta.issues_fixed || 0);

        if (added > 0 || resolved > 0) {
            filesChanged.push({
                path: file.file_path,
                added: added,
                resolved: resolved
            });
        }

        if (hasDetailed) {
            filteredAdded.forEach(issue => {
                allIssuesAdded.push({
                    type: issue.type || 'linter',
                    rule: issue.symbol || issue.rule || '',
                    message: issue.message || 'Unknown issue',
                    file: file.file_path,
                    line: issue.line || '-',
                    severity: issue.severity || 'warning',
                });
            });
        } else {
            if (delta.linter_errors_delta > 0) {
                allIssuesAdded.push({ type: 'linter', rule: 'errors', message: `+${delta.linter_errors_delta} linter error(s)`, file: file.file_path, line: '-', severity: 'error' });
            }
            if (delta.linter_warnings_delta > 0) {
                allIssuesAdded.push({ type: 'linter', rule: 'warnings', message: `+${delta.linter_warnings_delta} linter warning(s)`, file: file.file_path, line: '-', severity: 'warning' });
            }
        }

        if (hasDetailed) {
            filteredResolved.forEach(issue => {
                allIssuesResolved.push({
                    type: issue.type || 'linter',
                    rule: issue.symbol || issue.rule || '',
                    message: issue.message || 'Issue fixed',
                    file: file.file_path,
                    line: issue.line || '-',
                    severity: issue.severity || 'warning',
                });
            });
        } else {
            if (delta.linter_errors_delta < 0) {
                allIssuesResolved.push({ type: 'linter', rule: 'errors', message: `${Math.abs(delta.linter_errors_delta)} error(s) fixed`, file: file.file_path, line: '-', severity: 'error' });
            }
            if (delta.linter_warnings_delta < 0) {
                allIssuesResolved.push({ type: 'linter', rule: 'warnings', message: `${Math.abs(delta.linter_warnings_delta)} warning(s) fixed`, file: file.file_path, line: '-', severity: 'warning' });
            }
        }
    });

    // Sort issues: highest severity first, then by type (security first), then by file
    const sortIssues = (a, b) => {
        const sevDiff = _sevOrder(b.severity) - _sevOrder(a.severity);
        if (sevDiff !== 0) return sevDiff;
        // Security issues first within same severity
        const aIsSec = (a.type || '').toLowerCase() === 'security' || (a.type || '').toLowerCase() === 'bandit' ? 1 : 0;
        const bIsSec = (b.type || '').toLowerCase() === 'security' || (b.type || '').toLowerCase() === 'bandit' ? 1 : 0;
        if (bIsSec !== aIsSec) return bIsSec - aIsSec;
        return (a.file || '').localeCompare(b.file || '');
    };

    allIssuesAdded.sort(sortIssues);
    allIssuesResolved.sort(sortIssues);

    // Build severity summary for the header
    const addedSevSummary = _buildSeveritySummary(allIssuesAdded);
    const resolvedSevSummary = _buildSeveritySummary(allIssuesResolved);

    // Render issues added
    const addedList = document.getElementById('issues-added-list');
    document.getElementById('issues-added-count').textContent = allIssuesAdded.length;
    if (allIssuesAdded.length === 0) {
        addedList.innerHTML = '<p class="no-issues">No new issues introduced</p>';
    } else {
        addedList.innerHTML = addedSevSummary + allIssuesAdded.map(issue => renderIssueItem(issue, repo, fullSha)).join('');
    }

    // Render issues resolved
    const resolvedList = document.getElementById('issues-resolved-list');
    document.getElementById('issues-resolved-count').textContent = allIssuesResolved.length;
    if (allIssuesResolved.length === 0) {
        resolvedList.innerHTML = '<p class="no-issues">No issues resolved</p>';
    } else {
        resolvedList.innerHTML = resolvedSevSummary + allIssuesResolved.map(issue => renderIssueItem(issue, repo, fullSha)).join('');
    }

    // Render files changed (sorted by most issues)
    filesChanged.sort((a, b) => (b.added + b.resolved) - (a.added + a.resolved));
    const filesList = document.getElementById('files-changed-list');
    filesList.innerHTML = filesChanged.length === 0
        ? '<p class="no-issues">No files with issue changes</p>'
        : filesChanged.map(f => `
            <div class="file-item">
                <span class="file-path">${f.path}</span>
                <span class="file-stats">
                    ${f.added > 0 ? `<span class="negative">+${f.added}</span>` : ''}
                    ${f.resolved > 0 ? `<span class="positive">-${f.resolved}</span>` : ''}
                </span>
            </div>
        `).join('');

    // Set GitHub link
    const githubLink = document.getElementById('github-link');
    if (repo && fullSha) {
        githubLink.href = `https://github.com/${repo}/commit/${fullSha}`;
        githubLink.style.display = 'inline-block';
    } else {
        githubLink.style.display = 'none';
    }

    modal.style.display = 'flex';
}

/**
 * Build a compact severity summary bar (e.g., "3 high · 5 medium · 2 low")
 */
function _buildSeveritySummary(issues) {
    const counts = { high: 0, medium: 0, low: 0 };
    issues.forEach(i => {
        const norm = normalizeSeverity(i);
        counts[norm] = (counts[norm] || 0) + 1;
    });

    const parts = [];
    if (counts.high > 0)   parts.push(`<span class="sev-pill sev-pill-high">${counts.high} high</span>`);
    if (counts.medium > 0) parts.push(`<span class="sev-pill sev-pill-medium">${counts.medium} medium</span>`);
    if (counts.low > 0)    parts.push(`<span class="sev-pill sev-pill-low">${counts.low} low</span>`);

    if (parts.length === 0) return '';
    return `<div class="issue-sev-summary">${parts.join('')}</div>`;
}

/**
 * Render a single issue item with severity-colored border and badges
 */
function renderIssueItem(issue, repo, sha) {
    const line = issue.line || '?';
    const file = issue.file || '';
    const rule = issue.rule || 'unknown';
    const message = issue.message || '';
    const type = issue.type || 'issue';
    const severity = issue.severity || 'warning';

    const sev = _sevStyle(severity);
    const typeS = _typeStyle(type);

    let lineLink = `Line ${line}`;
    if (repo && sha && file && line !== '-' && line !== '?') {
        const githubUrl = `https://github.com/${repo}/blob/${sha}/${file}#L${line}`;
        lineLink = `<a href="${githubUrl}" target="_blank" class="line-link">Line ${line}</a>`;
    }

    return `
        <div class="issue-item" style="border-left-color: ${sev.border};">
            <div class="issue-header">
                <span class="issue-sev-badge" style="background:${sev.bg}; color:${sev.border};">${sev.label}</span>
                <span class="issue-type" style="background:${typeS.bg}; color:${typeS.color};">${typeS.label}</span>
                <span class="issue-rule">${rule}</span>
                <span class="issue-location">${lineLink} in <code>${file.split('/').pop()}</code></span>
            </div>
            <p class="issue-message">${message}</p>
        </div>
    `;
}

/**
 * Export data to CSV for research paper
 */
function exportToCSV() {
    // Build CSV content
    const headers = [
        'commit_sha', 'repo', 'ai_tool', 'files_analyzed',
        'issues_introduced', 'issues_fixed', 'net_change',
        'survival_rate', 'churn_rate', 'was_reverted', 
        'fix_rate', 'files_survived', 'files_modified'
    ];
    
    const rows = [];
    
    debtData.forEach((debt, i) => {
        const sha = debt.commit_hash || '';
        const lifecycle = lifecycleData[i] || {};
        const destiny = destinyData.find(d => d.commit && sha && d.commit.includes(sha.substring(0, 8))) || {};
        
        // Count file statuses
        let survived = 0, modified = 0;
        (lifecycle.files || []).forEach(f => {
            if (f.status === 'SURVIVED') survived++;
            else if (f.status === 'MODIFIED') modified++;
        });

        const issueCounts = getCommitIssueCounts(debt);
        
        rows.push([
            sha.substring(0, 12),
            debt.repo || '',
            debt.ai_tool || 'unknown',
            debt.code_files_analyzed || 0,
            issueCounts.introduced || 0,
            issueCounts.fixed || 0,
            (issueCounts.introduced || 0) - (issueCounts.fixed || 0),
            destiny.survival_rate?.toFixed(4) || '',
            lifecycle.churn?.churn_rate?.toFixed(4) || '',
            lifecycle.revert?.was_reverted ? 'true' : 'false',
            lifecycle.bug_fixes?.fix_rate?.toFixed(4) || '',
            survived,
            modified
        ]);
    });
    
    // Build CSV string
    let csv = headers.join(',') + '\n';
    rows.forEach(row => {
        csv += row.map(cell => `"${cell}"`).join(',') + '\n';
    });
    
    // Download
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai_code_analysis_${currentRepoPath.split('/').pop() || 'data'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}
