/**
 * AI Code Analysis Dashboard — Summary Cards & Issue Survival
 * renderSummaryCards, deep scan results, issue survival results, severity commit locator.
 */

/**
 * Render Summary Cards
 */
function renderSummaryCards() {
    const activeData = getActiveDebtData();
    const totalCommits = activeData.length;
    document.getElementById('total-commits').textContent = totalCommits;

    // Issues introduced (respect severity + role filter)
    const filtered = getFilteredIssueCounts();
    const introduced = filtered.introduced;
    const fixed = filtered.fixed;
    
    const debtEl = document.getElementById('net-debt');
    const displayText = introduced > 0 ? `+${introduced}` : '0';
    debtEl.textContent = showLowSeverity ? displayText : `${displayText}*`;
    debtEl.className = 'card-value ' + (introduced > 0 ? 'negative' : 'positive');
    // Add tooltip to indicate filtering
    debtEl.title = showLowSeverity ? '' : 'Excluding low severity issues';

    // Code survival rate (Line-based / Syntactic)
    let avgSurvival = researchSummary?.destiny?.avg_survival_rate;
    if (avgSurvival === undefined) {
        let totalSurvival = 0;
        destinyData.forEach(d => {
            totalSurvival += d.survival_rate || 0;
        });
        avgSurvival = destinyData.length > 0 ? totalSurvival / destinyData.length : 0;
    }
    const survivalEl = document.getElementById('survival-rate');
    survivalEl.textContent = `${(avgSurvival * 100).toFixed(1)}%`;
    survivalEl.className = 'card-value ' + (avgSurvival >= 0.8 ? 'positive' : avgSurvival >= 0.5 ? 'warning' : 'negative');

    // Semantic survival rate (AST-based)
    let avgSemanticSurvival = 0;
    let semanticCount = 0;
    destinyData.forEach(d => {
        if (d.semantic_survival_rate !== undefined && d.semantic_units_original > 0) {
            avgSemanticSurvival += d.semantic_survival_rate;
            semanticCount++;
        }
    });
    avgSemanticSurvival = semanticCount > 0 ? avgSemanticSurvival / semanticCount : avgSurvival;
    
    const semanticEl = document.getElementById('semantic-rate');
    if (semanticEl) {
        semanticEl.textContent = `${(avgSemanticSurvival * 100).toFixed(1)}%`;
        semanticEl.className = 'card-value ' + (avgSemanticSurvival >= 0.8 ? 'positive' : avgSemanticSurvival >= 0.5 ? 'warning' : 'negative');
        
        // Show delta (semantic vs syntactic)
        const deltaEl = document.getElementById('semantic-delta');
        if (deltaEl) {
            const delta = avgSemanticSurvival - avgSurvival;
            if (delta > 0.01) {
                deltaEl.textContent = `+${(delta * 100).toFixed(1)}% vs lines`;
                deltaEl.className = 'card-delta positive';
            } else if (delta < -0.01) {
                deltaEl.textContent = `${(delta * 100).toFixed(1)}% vs lines`;
                deltaEl.className = 'card-delta negative';
            } else {
                deltaEl.textContent = '';
            }
        }
    }

    // Churn rate (from research summary or lifecycle)
    let churnRate = researchSummary?.lifecycle?.avg_churn_rate || 0;
    if (churnRate === 0) {
        let totalChurn = 0;
        let churnCount = 0;
        lifecycleData.forEach(commit => {
            if (commit.churn?.churn_rate) {
                totalChurn += commit.churn.churn_rate;
                churnCount++;
            }
        });
        churnRate = churnCount > 0 ? totalChurn / churnCount : 0;
    }
    const churnEl = document.getElementById('churn-rate');
    churnEl.textContent = churnRate.toFixed(2);
    churnEl.className = 'card-value ' + (churnRate > 1 ? 'negative' : churnRate > 0.5 ? 'warning' : 'neutral');

    // Revert count
    let revertCount = researchSummary?.lifecycle?.total_reverts || 0;
    if (revertCount === 0) {
        lifecycleData.forEach(commit => {
            if (commit.revert?.was_reverted) revertCount++;
        });
    }
    const revertEl = document.getElementById('revert-count');
    revertEl.textContent = revertCount;
    revertEl.className = 'card-value ' + (revertCount > 0 ? 'negative' : 'positive');

    // Fix rate
    let fixRate = 0;
    let filesWithFixes = researchSummary?.lifecycle?.files_fixed || 0;
    let totalFiles = (researchSummary?.lifecycle?.files_survived || 0) + 
                     (researchSummary?.lifecycle?.files_modified || 0) + 
                     (researchSummary?.lifecycle?.files_deleted || 0);
    if (totalFiles > 0) {
        fixRate = filesWithFixes / totalFiles;
    } else {
        // Calculate from lifecycle data
        let filesNeedingFixes = 0;
        totalFiles = 0;
        lifecycleData.forEach(commit => {
            (commit.files || []).forEach(f => {
                totalFiles++;
                if (f.was_fixed) filesNeedingFixes++;
            });
        });
        fixRate = totalFiles > 0 ? filesNeedingFixes / totalFiles : 0;
    }
    const fixEl = document.getElementById('fix-rate');
    fixEl.textContent = `${(fixRate * 100).toFixed(1)}%`;
    fixEl.className = 'card-value ' + (fixRate > 0.3 ? 'negative' : fixRate > 0.1 ? 'warning' : 'positive');

    // Render deep scan results if available
    renderDeepScanResults();
    
    // Render issue survival results (KEY RESEARCH METRIC)
    renderIssueSurvivalResults();
}

/**
 * Render Deep Scan Results (CodeQL/SonarQube)
 */
function renderDeepScanResults() {
    const section = document.getElementById('deep-scan-section');
    if (!section) return;

    // Check if we have deep scan data
    if (!deepScanData || Object.keys(deepScanData).length === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';

    // Determine analysis mode
    const mode = deepScanData.analysis_mode || 'unknown';
    const modeEl = document.getElementById('deep-scan-mode');
    if (modeEl) {
        if (mode === 'before_after') {
            modeEl.textContent = 'Before/After';
            modeEl.className = 'card-value positive';
        } else if (mode === 'current_head') {
            modeEl.textContent = 'Current HEAD';
            modeEl.className = 'card-value warning';
        } else {
            modeEl.textContent = mode;
        }
    }

    // Commits analyzed
    const commitsEl = document.getElementById('deep-scan-commits');
    if (commitsEl) {
        const commits = deepScanData.commits_analyzed || deepScanData.ai_commits_analyzed || 0;
        commitsEl.textContent = commits;
    }

    // Issues introduced/fixed (for before_after mode)
    const introducedEl = document.getElementById('deep-scan-introduced');
    const fixedEl = document.getElementById('deep-scan-fixed');
    const netEl = document.getElementById('deep-scan-net');

    // Calculate how many issues to subtract when low-severity filter is active.
    // Deep scan by_severity maps severity names → counts.  We subtract low-severity
    // counts from the headline totals when the filter is off.
    let lowSevAdjustment = 0;
    if (!showLowSeverity) {
        const dsSummary = deepScanData.summary || {};
        const dsBySeverity = dsSummary.by_severity || {};
        Object.entries(dsBySeverity).forEach(([sev, count]) => {
            if (isLowSeverityCategory(sev)) {
                lowSevAdjustment += (typeof count === 'number' ? count : 0);
            }
        });
    }

    if (mode === 'before_after') {
        const summary = deepScanData.summary || {};
        let introduced = summary.total_introduced || deepScanData.total_issues_introduced || 0;
        const fixed = summary.total_fixed || deepScanData.total_issues_fixed || 0;
        // Subtract low-severity from introduced (conservative: low-sev issues are predominantly introduced)
        introduced = Math.max(0, introduced - lowSevAdjustment);
        const net = introduced - fixed;

        if (introducedEl) {
            introducedEl.textContent = `+${introduced}`;
            introducedEl.className = 'card-value ' + (introduced > 0 ? 'negative' : 'positive');
        }
        if (fixedEl) {
            fixedEl.textContent = `-${fixed}`;
            fixedEl.className = 'card-value positive';
        }
        if (netEl) {
            netEl.textContent = net > 0 ? `+${net}` : net;
            netEl.className = 'card-value ' + (net > 0 ? 'negative' : net < 0 ? 'positive' : 'neutral');
        }
    } else {
        // Current HEAD mode - show AI issues count
        let aiIssues = deepScanData.ai_issues_count || 0;
        let totalIssues = deepScanData.combined?.total_issues || 0;
        aiIssues = Math.max(0, aiIssues - lowSevAdjustment);
        totalIssues = Math.max(0, totalIssues - lowSevAdjustment);

        if (introducedEl) {
            introducedEl.textContent = aiIssues;
            introducedEl.className = 'card-value ' + (aiIssues > 0 ? 'warning' : 'positive');
        }
        if (fixedEl) {
            fixedEl.textContent = '-';
        }
        if (netEl) {
            netEl.textContent = `${totalIssues} total`;
            netEl.className = 'card-value neutral';
        }
    }

    // Render details
    renderDeepScanDetails();
}

/**
 * Render Deep Scan Details (issues list, by severity, by tool)
 */
function renderDeepScanDetails() {
    const container = document.getElementById('deep-scan-details');
    if (!container) return;

    let html = '<div class="deep-scan-grid">';

    // Tools used
    const tools = deepScanData.tools_used || [];
    html += `<div class="deep-scan-panel">
        <h4>🔧 Tools Used</h4>
        <ul>${tools.map(t => `<li>${t}</li>`).join('') || '<li>None</li>'}</ul>
    </div>`;

    // By severity — filter out low-severity rows when toggle is off
    const summary = deepScanData.summary || {};
    const bySeverity = summary.by_severity || {};
    const filteredDsSevEntries = Object.entries(bySeverity)
        .filter(([sev]) => showLowSeverity || !isLowSeverityCategory(sev));
    if (filteredDsSevEntries.length > 0) {
        html += `<div class="deep-scan-panel">
            <h4>📊 By Severity</h4>
            <ul>${filteredDsSevEntries.map(([sev, count]) => 
                `<li><span class="severity-${sev.toLowerCase()}">${sev}</span>: ${count}</li>`
            ).join('')}</ul>
        </div>`;
    }

    // By type
    const byType = summary.by_type || {};
    if (Object.keys(byType).length > 0) {
        html += `<div class="deep-scan-panel">
            <h4>📋 By Type</h4>
            <ul>${Object.entries(byType).map(([type, count]) => 
                `<li>${type}: ${count}</li>`
            ).join('')}</ul>
        </div>`;
    }

    // CodeQL results
    if (deepScanData.codeql) {
        const codeql = deepScanData.codeql;
        html += `<div class="deep-scan-panel">
            <h4>🔍 CodeQL</h4>
            <p>Issues: ${codeql.issue_count || 0}</p>
            ${codeql.by_severity ? `<p>Severity: ${JSON.stringify(codeql.by_severity)}</p>` : ''}
        </div>`;
    }

    // SonarQube results
    if (deepScanData.sonarqube) {
        const sonar = deepScanData.sonarqube;
        const metrics = sonar.metrics || {};
        html += `<div class="deep-scan-panel">
            <h4>📡 SonarQube</h4>
            <ul>
                <li>Bugs: ${metrics.bugs || 0}</li>
                <li>Vulnerabilities: ${metrics.vulnerabilities || 0}</li>
                <li>Code Smells: ${metrics.code_smells || 0}</li>
                <li>Security Hotspots: ${metrics.security_hotspots || 0}</li>
                <li>Tech Debt: ${sonar.tech_debt_minutes || 0} min</li>
            </ul>
        </div>`;
    }

    // Commits with issues (for before_after mode)
    const commits = deepScanData.commits || [];
    const commitsWithIssues = commits.filter(c => (c.issues_introduced_count || 0) > 0);
    if (commitsWithIssues.length > 0) {
        html += `<div class="deep-scan-panel wide">
            <h4>⚠️ Commits That Introduced Issues</h4>
            <table class="mini-table">
                <tr><th>Commit</th><th>Introduced</th><th>Fixed</th><th>Net</th></tr>
                ${commitsWithIssues.slice(0, 10).map(c => `
                    <tr>
                        <td><code>${(c.commit || '').substring(0, 8)}</code></td>
                        <td class="negative">+${c.issues_introduced_count || 0}</td>
                        <td class="positive">-${c.issues_fixed_count || 0}</td>
                        <td>${c.net_change || 0}</td>
                    </tr>
                `).join('')}
            </table>
            ${commitsWithIssues.length > 10 ? `<p class="hint">...and ${commitsWithIssues.length - 10} more</p>` : ''}
        </div>`;
    }

    html += '</div>';
    container.innerHTML = html;
}

/**
 * Render Issue Survival Results (KEY RESEARCH METRIC)
 * Shows what percentage of AI-introduced issues still exist at HEAD
 */
function renderIssueSurvivalResults() {
    const section = document.getElementById('issue-survival-section');
    if (!section) return;

    // Check if we have issue survival data
    const survivalSummary = summarizeFilteredIssueSurvival();
    if (!issueSurvivalData || Object.keys(issueSurvivalData).length === 0 || survivalSummary.totalIssues === 0) {
        section.style.display = 'none';
        return;
    }

    section.style.display = 'block';

    const totalIssues = survivalSummary.totalIssues;
    const survivingIssues = survivalSummary.survivingIssues;
    const fixedIssues = survivalSummary.fixedIssues;

    // Total issues
    const totalEl = document.getElementById('survival-total-issues');
    if (totalEl) {
        totalEl.textContent = totalIssues;
    }

    // Surviving issues
    const survivingEl = document.getElementById('survival-surviving');
    if (survivingEl) {
        survivingEl.textContent = survivingIssues;
        survivingEl.className = 'card-value ' + (survivingIssues > 0 ? 'warning' : 'positive');
    }

    // Fixed issues
    const fixedEl = document.getElementById('survival-fixed');
    if (fixedEl) {
        fixedEl.textContent = fixedIssues;
        fixedEl.className = 'card-value positive';
    }

    // Survival rate (KEY METRIC) - recalculated from filtered values
    const rateEl = document.getElementById('survival-rate-value');
    if (rateEl) {
        const rate = totalIssues > 0 ? (survivingIssues / totalIssues) * 100 : 0;
        rateEl.textContent = `${rate.toFixed(1)}%`;
        // Lower is better - issues getting fixed
        rateEl.className = 'card-value ' + (rate > 70 ? 'negative' : rate > 40 ? 'warning' : 'positive');
    }

    // Render detailed breakdown
    renderIssueSurvivalDetails();
}

/**
 * Render Issue Survival Details (by severity, by rule)
 */
function renderIssueSurvivalDetails() {
    const container = document.getElementById('issue-survival-details');
    if (!container) return;

    let html = '<div class="survival-grid">';

    // By severity — filter out low-severity rows when toggle is off
    // Rows are CLICKABLE: clicking a severity shows commits that have issues of that severity.
    const survivalSummary = summarizeFilteredIssueSurvival();
    const bySeverity = survivalSummary.bySeverity || {};
    const filteredSeverityEntries = Object.entries(bySeverity)
        .filter(([sev]) => showLowSeverity || !isLowSeverityCategory(sev));

    if (filteredSeverityEntries.length > 0) {
        html += `<div class="survival-panel">
            <h4>📊 By Severity <span class="hint">(click to locate commits)</span></h4>
            <table class="mini-table">
                <tr><th>Severity</th><th>Total</th><th>Surviving</th><th>Rate</th></tr>
                ${filteredSeverityEntries.map(([sev, data]) => `
                    <tr class="clickable-row severity-locator" data-severity="${sev}">
                        <td><span class="severity-${sev.toLowerCase()}">${sev}</span></td>
                        <td>${data.total || 0}</td>
                        <td>${data.surviving || 0}</td>
                        <td class="${(data.rate || 0) > 0.5 ? 'negative' : 'positive'}">${((data.rate || 0) * 100).toFixed(1)}%</td>
                    </tr>
                `).join('')}
            </table>
            <div id="severity-commit-locator" class="severity-locator-results"></div>
        </div>`;
    }

    // By rule (top surviving) — use isLowSeverityRule() which checks both
    // the issues array data AND the known-rules list.
    const byRule = survivalSummary.byRule || {};
    let ruleEntries = Object.entries(byRule);
    if (!showLowSeverity) {
        ruleEntries = ruleEntries.filter(([ruleName, data]) => {
            // Check the rule severity map (built from issues + known rules)
            if (isLowSeverityRule(ruleName)) return false;
            // Also check explicit flags on the data itself (if present)
            const ruleSev = (data.severity || '').toString().toLowerCase();
            if (ruleSev && isLowSeverityCategory(ruleSev)) return false;
            if (data._is_low_severity === true) return false;
            return true;
        });
    }
    const sortedRules = ruleEntries
        .sort((a, b) => (b[1].surviving || 0) - (a[1].surviving || 0))
        .slice(0, 10);

    if (sortedRules.length > 0) {
        html += `<div class="survival-panel">
            <h4>🔍 Top Surviving Issue Types</h4>
            <table class="mini-table">
                <tr><th>Rule</th><th>Total</th><th>Surviving</th><th>Rate</th></tr>
                ${sortedRules.map(([rule, data]) => `
                    <tr>
                        <td><code>${rule}</code></td>
                        <td>${data.total || 0}</td>
                        <td>${data.surviving || 0}</td>
                        <td class="${(data.rate || 0) > 0.5 ? 'negative' : 'positive'}">${((data.rate || 0) * 100).toFixed(1)}%</td>
                    </tr>
                `).join('')}
            </table>
        </div>`;
    }

    html += '</div>';
    container.innerHTML = html;

    // Attach click handlers for severity locator rows
    container.querySelectorAll('.severity-locator').forEach(row => {
        row.addEventListener('click', () => {
            const sev = row.dataset.severity;
            showCommitsForSeverity(sev);
        });
    });
}

/**
 * Show commits that contain issues of a given severity.
 * Renders a small list below the severity table.
 */
function showCommitsForSeverity(targetSeverity) {
    const locator = document.getElementById('severity-commit-locator');
    if (!locator) return;

    const targetLower = targetSeverity.toLowerCase();

    // Scan debt data to find commits with issues matching this severity
    const matchingCommits = [];
    debtData.forEach((commit) => {
        let matchCount = 0;
        const files = commit.files || [];
        files.forEach(file => {
            const added = getVisibleFileIssues(file, 'issues_added');
            added.forEach(issue => {
                const issueSev = (issue.severity || '').toString().toLowerCase();
                if (issueSev === targetLower) matchCount++;
            });
        });
        if (matchCount > 0) {
            matchingCommits.push({
                sha: (commit.commit_hash || '').substring(0, 8),
                fullSha: commit.commit_hash || '',
                repo: commit.repo || '',
                tool: commit.ai_tool || 'unknown',
                count: matchCount,
                commit
            });
        }
    });

    // Also scan issue survival issues array for more accurate matching
    const survivalIssues = getFilteredSurvivalEntries();
    const commitShaSet = new Set(matchingCommits.map(c => c.sha));
    survivalIssues.forEach(entry => {
        const orig = entry.original || {};
        const issueSev = (orig.severity || '').toString().toLowerCase();
        if (issueSev !== targetLower) return;
        const sha = (orig.commit_sha || '').substring(0, 8);
        if (sha && !commitShaSet.has(sha)) {
            // Find the commit in debtData
            const commit = debtData.find(c => (c.commit_hash || '').startsWith(sha));
            if (commit) {
                matchingCommits.push({
                    sha,
                    fullSha: commit.commit_hash || '',
                    repo: commit.repo || '',
                    tool: commit.ai_tool || 'unknown',
                    count: 1,
                    commit
                });
                commitShaSet.add(sha);
            }
        }
    });

    // Sort by count descending
    matchingCommits.sort((a, b) => b.count - a.count);

    if (matchingCommits.length === 0) {
        locator.innerHTML = `<p class="hint-text" style="margin-top:0.75rem;">No commits found with <strong>${targetSeverity}</strong> issues in current data.</p>`;
        return;
    }

    locator.innerHTML = `
        <div class="severity-locator-panel">
            <div class="severity-locator-header">
                <strong>${targetSeverity}</strong> issues found in ${matchingCommits.length} commit${matchingCommits.length === 1 ? '' : 's'}
                <span class="severity-locator-close" onclick="this.closest('.severity-locator-results').innerHTML=''">&times;</span>
            </div>
            ${matchingCommits.slice(0, 8).map(c => `
                <div class="hotspot-item severity-commit-item" data-sha="${c.sha}">
                    <div>
                        <div><code>${c.sha}</code> <span class="hotspot-meta">${c.tool}</span></div>
                        <div class="hotspot-meta">${c.repo.split('/').pop() || ''}</div>
                    </div>
                    <div class="hotspot-count">${c.count} issue${c.count === 1 ? '' : 's'}</div>
                </div>
            `).join('')}
            ${matchingCommits.length > 8 ? `<p class="hint" style="padding:0.4rem 0.75rem;">...and ${matchingCommits.length - 8} more</p>` : ''}
        </div>
    `;

    // Make items clickable to open commit details
    locator.querySelectorAll('.severity-commit-item').forEach(el => {
        el.addEventListener('click', () => {
            const sha = el.dataset.sha;
            const commit = matchingCommits.find(c => c.sha === sha);
            if (commit && commit.commit) showCommitDetails(commit.commit);
        });
    });
}
