/**
 * AI Code Analysis Dashboard — Tables
 * File destiny table, file detail modal, commits table.
 */

/**
 * Render Tables
 */
function renderTables() {
    renderFileTable();
    renderCommitsTable();
    renderHighSeverityHotspots();
}

// Pagination state for file table
let _fileTablePage = 0;
const FILE_TABLE_PAGE_SIZE = 50;

function renderFileTable() {
    const tbody = document.getElementById('file-tbody');
    const summaryEl = document.getElementById('file-stability-summary');
    const countEl = document.getElementById('file-table-count');
    const paginationEl = document.getElementById('file-table-pagination');
    tbody.innerHTML = '';

    // Flatten all file records from destiny data
    let allFiles = [];
    destinyData.forEach(commit => {
        const shortSha = commit.commit?.substring(0, 8) || '-';
        const repo = commit.repo || '';
        const fullSha = commit.commit || '';

        (commit.file_details || []).forEach(file => {
            const lineSurvival = file.lines_added > 0
                ? (file.lines_exist / file.lines_added)
                : 0;
            const semantic = file.semantic || {};
            const semanticRate = semantic.semantic_survival_rate !== undefined
                ? semantic.semantic_survival_rate : null;
            const modCount = file.modification_count || 0;
            const status = semanticRate !== null
                ? (semanticRate >= 0.8 ? 'stable' : 'modified')
                : (lineSurvival >= 0.8 ? 'stable' : 'modified');
            // Treat lines_exist=0 + lines_added>0 as deleted
            const isDeleted = file.lines_added > 0 && file.lines_exist === 0;

            allFiles.push({
                file, commit, repo, fullSha, shortSha,
                lineSurvival, semanticRate, modCount,
                status: isDeleted ? 'deleted' : status,
                linesAdded: file.lines_added || 0,
            });
        });
    });

    // Compute summary stats
    const totalFiles = allFiles.length;
    const stableCount = allFiles.filter(f => f.status === 'stable').length;
    const modifiedCount = allFiles.filter(f => f.status === 'modified').length;
    const deletedCount = allFiles.filter(f => f.status === 'deleted').length;
    const avgSurvival = totalFiles > 0
        ? allFiles.reduce((s, f) => s + f.lineSurvival, 0) / totalFiles
        : 0;

    // Render summary cards
    if (summaryEl) {
        summaryEl.innerHTML = `
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value" style="font-size:1.3rem;">${totalFiles}</div>
                <div class="card-label">Total Files</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value positive" style="font-size:1.3rem;">${stableCount}</div>
                <div class="card-label">Stable (>80%)</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value warning" style="font-size:1.3rem;">${modifiedCount}</div>
                <div class="card-label">Modified</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value negative" style="font-size:1.3rem;">${deletedCount}</div>
                <div class="card-label">Deleted</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value" style="font-size:1.3rem;">${(avgSurvival * 100).toFixed(1)}%</div>
                <div class="card-label">Avg Survival</div>
            </div>
        `;
    }

    if (totalFiles === 0) {
        if (countEl) countEl.textContent = '(no data)';
        tbody.innerHTML = '<tr><td colspan="7" class="no-issues">No file destiny data available. Re-run the pipeline to generate.</td></tr>';
        if (paginationEl) paginationEl.innerHTML = '';
        return;
    }

    // Sort
    const sortBy = document.getElementById('file-sort')?.value || 'most-changed';
    if (sortBy === 'most-changed') {
        allFiles.sort((a, b) => b.modCount - a.modCount || b.linesAdded - a.linesAdded);
    } else if (sortBy === 'lowest-survival') {
        allFiles.sort((a, b) => a.lineSurvival - b.lineSurvival);
    } else if (sortBy === 'most-lines') {
        allFiles.sort((a, b) => b.linesAdded - a.linesAdded);
    } else if (sortBy === 'deleted-first') {
        allFiles.sort((a, b) => (b.status === 'deleted' ? 1 : 0) - (a.status === 'deleted' ? 1 : 0) || b.modCount - a.modCount);
    }

    // Paginate
    const totalPages = Math.ceil(allFiles.length / FILE_TABLE_PAGE_SIZE);
    if (_fileTablePage >= totalPages) _fileTablePage = 0;
    const start = _fileTablePage * FILE_TABLE_PAGE_SIZE;
    const pageFiles = allFiles.slice(start, start + FILE_TABLE_PAGE_SIZE);

    if (countEl) {
        countEl.textContent = `(${start + 1}-${Math.min(start + FILE_TABLE_PAGE_SIZE, totalFiles)} of ${totalFiles})`;
    }

    // Render rows
    pageFiles.forEach(({ file, commit, repo, fullSha, shortSha, lineSurvival, semanticRate, status }) => {
        const semantic = file.semantic || {};
        const semanticDisplay = semanticRate !== null ? (semanticRate * 100).toFixed(1) : '-';
        const survivedNames = semantic.survived_names || [];

        let commitLink = `<code>${shortSha}</code>`;
        if (repo && fullSha) {
            commitLink = `<a href="https://github.com/${repo}/commit/${fullSha}" target="_blank" class="commit-link"><code>${shortSha}</code></a>`;
        }

        let survivingUnitsDisplay = '-';
        if (survivedNames.length > 0) {
            const displayNames = survivedNames.slice(0, 3).map(n => `<code>${n}</code>`).join(', ');
            survivingUnitsDisplay = displayNames + (survivedNames.length > 3 ? ` +${survivedNames.length - 3} more` : '');
        } else if (semantic.supported === false) {
            survivingUnitsDisplay = '<span class="hint">N/A</span>';
        }

        const badgeClass = status === 'deleted' ? 'low' : status === 'stable' ? 'stable' : 'modified';

        const tr = document.createElement('tr');
        tr.className = 'clickable-row';
        tr.innerHTML = `
            <td>${commitLink}</td>
            <td>${file.file}</td>
            <td>${file.lines_added}</td>
            <td>${file.lines_exist} <small class="hint">(${(lineSurvival * 100).toFixed(1)}%)</small></td>
            <td class="${semantic.semantic_vs_syntactic_delta > 0.05 ? 'semantic-boost' : ''}">${semanticDisplay}%</td>
            <td class="surviving-units">${survivingUnitsDisplay}</td>
            <td><span class="badge badge-${badgeClass}">${status}</span></td>
        `;
        tr.onclick = (e) => {
            if (e.target.tagName === 'A') return;
            showFileDetails(file, commit, repo, fullSha);
        };
        tbody.appendChild(tr);
    });

    // Render pagination
    if (paginationEl && totalPages > 1) {
        paginationEl.innerHTML = `
            <button class="evolution-btn" ${_fileTablePage === 0 ? 'disabled' : ''} onclick="_fileTablePage=0; renderFileTable();">First</button>
            <button class="evolution-btn" ${_fileTablePage === 0 ? 'disabled' : ''} onclick="_fileTablePage--; renderFileTable();">Prev</button>
            <span class="hint" style="padding:0 0.75rem;">Page ${_fileTablePage + 1} of ${totalPages}</span>
            <button class="evolution-btn" ${_fileTablePage >= totalPages - 1 ? 'disabled' : ''} onclick="_fileTablePage++; renderFileTable();">Next</button>
            <button class="evolution-btn" ${_fileTablePage >= totalPages - 1 ? 'disabled' : ''} onclick="_fileTablePage=${totalPages - 1}; renderFileTable();">Last</button>
        `;
    } else if (paginationEl) {
        paginationEl.innerHTML = '';
    }
}

async function showFileDetails(file, commit, repo, fullSha) {
    const modal = document.getElementById('file-modal');
    const shortSha = fullSha?.substring(0, 8) || '-';

    // Set header
    document.getElementById('file-modal-info').innerHTML = `
        <strong>File:</strong> <code>${file.file}</code> | 
        <strong>Commit:</strong> <code>${shortSha}</code> | 
        <strong>Repo:</strong> ${repo}
    `;

    // Calculate stats
    const lineSurvival = file.lines_added > 0 ? ((file.lines_exist / file.lines_added) * 100).toFixed(1) : '0';
    
    // Get semantic data
    const semantic = file.semantic || {};
    const semanticSurvival = semantic.semantic_survival_rate !== undefined
        ? (semantic.semantic_survival_rate * 100).toFixed(1)
        : '-';
    const survivedNames = semantic.survived_names || [];
    const modifiedNames = semantic.modified_names || [];
    const deletedNames = semantic.deleted_names || [];

    // Show survival stats with both syntactic and semantic
    let statsHtml = `
        <div class="stat-item">
            <span class="stat-value">${file.lines_added}</span>
            <span class="stat-label">Lines Added</span>
        </div>
        <div class="stat-item">
            <span class="stat-value">${lineSurvival}%</span>
            <span class="stat-label">Line Survival</span>
        </div>
        <div class="stat-item">
            <span class="stat-value ${semantic.semantic_survival_rate >= 0.8 ? 'positive' : ''}">${semanticSurvival}%</span>
            <span class="stat-label">Semantic Survival</span>
        </div>
    `;
    
    // Add semantic delta if significant
    if (semantic.semantic_vs_syntactic_delta > 0.01) {
        statsHtml += `
        <div class="stat-item">
            <span class="stat-value positive">+${(semantic.semantic_vs_syntactic_delta * 100).toFixed(1)}%</span>
            <span class="stat-label">Refactoring Resilience</span>
        </div>
        `;
    }
    
    document.getElementById('file-survival-stats').innerHTML = statsHtml;
    
    // Show surviving functions/classes
    if (survivedNames.length > 0 || modifiedNames.length > 0 || deletedNames.length > 0) {
        let semanticHtml = '<div class="semantic-units">';
        if (survivedNames.length > 0) {
            semanticHtml += `<div class="unit-group"><strong>✓ Survived:</strong> ${survivedNames.map(n => `<code>${n}</code>`).join(', ')}</div>`;
        }
        if (modifiedNames.length > 0) {
            semanticHtml += `<div class="unit-group warning"><strong>~ Modified:</strong> ${modifiedNames.map(n => `<code>${n}</code>`).join(', ')}</div>`;
        }
        if (deletedNames.length > 0) {
            semanticHtml += `<div class="unit-group negative"><strong>✗ Deleted:</strong> ${deletedNames.map(n => `<code>${n}</code>`).join(', ')}</div>`;
        }
        semanticHtml += '</div>';
        document.getElementById('file-survival-stats').innerHTML += semanticHtml;
    }

    // Load lifecycle debug data
    const debug = debugData[shortSha.substring(0, 12)] || debugData[fullSha?.substring(0, 12)] || {};
    const lifecycleDebug = debug.lifecycle_debug || {};
    const fileLifecycle = lifecycleDebug[file.file] || {};
    const subsequentCommits = fileLifecycle.subsequent_commits || [];

    document.getElementById('changes-count').textContent = subsequentCommits.length;

    const commitsList = document.getElementById('subsequent-commits-list');
    if (subsequentCommits.length === 0) {
        commitsList.innerHTML = '<p class="no-issues">No subsequent changes - code is stable! ✓</p>';
    } else {
        commitsList.innerHTML = subsequentCommits.map(c => {
            const date = new Date(c.timestamp * 1000).toLocaleDateString();
            const commitUrl = `https://github.com/${repo}/commit/${c.sha}`;
            const tags = [];
            if (c.is_fix) tags.push('<span class="tag tag-fix">FIX</span>');
            if (c.is_refactor) tags.push('<span class="tag tag-refactor">REFACTOR</span>');

            return `
                <div class="commit-item">
                    <div class="commit-header">
                        <a href="${commitUrl}" target="_blank" class="commit-sha"><code>${c.sha.substring(0, 8)}</code></a>
                        <span class="commit-date">${date}</span>
                        ${tags.join('')}
                    </div>
                    <div class="commit-author">
                        👤 ${c.author}
                    </div>
                    <div class="commit-message">${c.message.substring(0, 100)}${c.message.length > 100 ? '...' : ''}</div>
                </div>
            `;
        }).join('');
    }

    // Set file GitHub link
    const fileLink = document.getElementById('file-github-link');
    if (repo && fullSha) {
        fileLink.href = `https://github.com/${repo}/blob/${fullSha}/${file.file}`;
        fileLink.style.display = 'inline-block';
    } else {
        fileLink.style.display = 'none';
    }

    modal.style.display = 'flex';
}

function renderCommitsTable() {
    const tbody = document.getElementById('commits-tbody');
    tbody.innerHTML = '';

    let rows = 0;
    getActiveDebtData().forEach((commit, i) => {
        const destiny = destinyData.find(d => d.commit && commit.commit_hash &&
            d.commit.includes(commit.commit_hash.substring(0, 8)));

        const counts = getCommitIssueCounts(commit);
        const introduced = counts.introduced;
        const fixed = counts.fixed;
        if (commitsDebtChangesOnly && introduced === 0 && fixed === 0) return;

        const net = introduced - fixed;
        const lineSurvival = destiny ? (destiny.survival_rate * 100).toFixed(1) + '%' : '-';
        const semanticSurvival = destiny?.semantic_survival_rate !== undefined 
            ? (destiny.semantic_survival_rate * 100).toFixed(1) + '%' 
            : '-';
        const valuation = destiny?.developer_valuation || '-';
        const repo = commit.repo || '';

        // Calculate semantic delta for highlighting
        const semanticDelta = destiny?.semantic_vs_syntactic_delta || 0;
        const semanticClass = semanticDelta > 0.05 ? 'semantic-boost' : '';

        // Calculate security and complexity for this commit
        let securityCount = 0;
        let complexitySum = 0;
        (commit.files || []).forEach(f => {
            const after = f.after || {};
            securityCount += after.security_total || 0;
            complexitySum += after.cognitive_complexity || 0;
        });

        const role = commit.author_role || 'unknown';
        const roleBadgeCls = role === 'sole_author' ? 'role-badge-sole' : role === 'coauthor' ? 'role-badge-co' : 'role-badge-unk';
        const roleLabel = role === 'sole_author' ? 'Single' : role === 'coauthor' ? 'Multi' : '?';

        const tr = document.createElement('tr');
        tr.className = 'clickable-row';
        tr.dataset.commitSha = commit.commit_hash;
        tr.dataset.repo = repo;
        tr.innerHTML = `
            <td><code>${(commit.commit_hash || '').substring(0, 8)}</code></td>
            <td class="repo-name">${repo.split('/').pop() || '-'}</td>
            <td>${commit.ai_tool || 'unknown'}</td>
            <td><span class="role-badge ${roleBadgeCls}">${roleLabel}</span></td>
            <td>${commit.code_files_analyzed || 0}</td>
            <td class="${introduced > 0 ? 'negative' : ''}">+${introduced}</td>
            <td class="${fixed > 0 ? 'positive' : ''}">-${fixed}</td>
            <td class="${net > 0 ? 'negative' : net < 0 ? 'positive' : 'neutral'}">${net > 0 ? '+' : ''}${net}</td>
            <td class="${securityCount > 0 ? 'negative' : ''}">${securityCount > 0 ? '🔒' + securityCount : '-'}</td>
            <td>${lineSurvival}</td>
            <td class="${semanticClass}">${semanticSurvival}${semanticDelta > 0.05 ? ' <span class="delta-indicator">+' + (semanticDelta * 100).toFixed(0) + '%</span>' : ''}</td>
            <td><span class="badge badge-${valuation.toLowerCase()}">${valuation}</span></td>
        `;
        tr.onclick = () => showCommitDetails(commit);
        tbody.appendChild(tr);
        rows += 1;
    });

    if (rows === 0) {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td class="no-issues" colspan="12">No commits match this filter.</td>`;
        tbody.appendChild(tr);
    }
}
