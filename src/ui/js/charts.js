/**
 * AI Code Analysis Dashboard — Charts
 * All Chart.js and SVG chart rendering (debt, tool, valuation, timeline, evolution).
 */

/**
 * Render Charts
 */
function renderCharts() {
    renderDebtChart();
    renderToolChart();
    renderValuationChart();
    renderTimelineChart();
    renderEvolutionTimeline();
}

// Evolution timeline zoom state
let evolutionZoom = 1;

function zoomEvolution(action) {
    if (action === 'in') evolutionZoom = Math.min(evolutionZoom * 1.3, 3);
    else if (action === 'out') evolutionZoom = Math.max(evolutionZoom / 1.3, 0.5);
    else evolutionZoom = 1;
    renderEvolutionTimeline();
}

/**
 * Render Evolution Timeline - Clean Up/Down Bar Visualization with Tool Colors
 */
function renderEvolutionTimeline() {
    const container = document.getElementById('evolution-container');
    const svg = document.getElementById('evolution-svg');
    const tooltip = document.getElementById('evolution-tooltip');
    const statsContainer = document.getElementById('evolution-stats');
    
    if (!svg || !container) {
        console.warn('[Dashboard] evolution-svg not found');
        return;
    }

    const activeData = getActiveDebtData();
    if (!activeData || activeData.length === 0) {
        svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle" fill="#a0a0c0">No commit data available</text>';
        return;
    }

    // AI Tool color scheme (matches new palette)
    const toolColors = {
        'copilot': { intro: '#ef476f', fix: '#ff6b8a' },
        'claude': { intro: '#a78bfa', fix: '#c4b5fd' },
        'coderabbit': { intro: '#818cf8', fix: '#a5b4fc' },
        'cursor': { intro: '#34d399', fix: '#6ee7b7' },
        'gemini': { intro: '#fbbf24', fix: '#fcd34d' },
        'unknown': { intro: '#71717a', fix: '#a1a1aa' }
    };

    // Process all commits with cumulative debt
    let cumulative = 0;
    const commits = activeData.map((commit, i) => {
        const counts = getCommitIssueCounts(commit);
        const introduced = counts.introduced;
        const fixed = counts.fixed;
        const net = introduced - fixed;
        cumulative += net;
        const tool = (commit.ai_tool || 'unknown').toLowerCase();
        return {
            index: i,
            sha: (commit.commit_hash || '').substring(0, 7),
            fullSha: commit.commit_hash || '',
            tool: tool,
            toolDisplay: commit.ai_tool || 'unknown',
            colors: toolColors[tool] || toolColors['unknown'],
            introduced,
            fixed,
            net,
            cumulative,
            impact: Math.abs(net),
            commit
        };
    });

    // Calculate stats
    const totalIntro = commits.reduce((s, c) => s + c.introduced, 0);
    const totalFixed = commits.reduce((s, c) => s + c.fixed, 0);
    const finalDebt = commits[commits.length - 1]?.cumulative || 0;
    const peakDebt = Math.max(...commits.map(c => c.cumulative));
    
    // Tool usage stats
    const toolCounts = {};
    commits.forEach(c => {
        toolCounts[c.toolDisplay] = (toolCounts[c.toolDisplay] || 0) + 1;
    });
    const topTool = Object.keys(toolCounts).reduce((a, b) => toolCounts[a] > toolCounts[b] ? a : b, 'unknown');

    // Render stats with tool info
    const toolsList = Object.keys(toolCounts)
        .sort((a, b) => toolCounts[b] - toolCounts[a])
        .map(tool => {
            const c = commits.find(cm => cm.toolDisplay === tool);
            return `<span style="color: ${c.colors.intro}; margin-right: 8px;">● ${tool} (${toolCounts[tool]})</span>`;
        })
        .join('');
    
    statsContainer.innerHTML = `
        <div class="evolution-stat">
            <div class="evolution-stat-value neutral">${commits.length}</div>
            <div class="evolution-stat-label">AI Commits</div>
        </div>
        <div class="evolution-stat">
            <div class="evolution-stat-value positive">+${totalIntro}</div>
            <div class="evolution-stat-label">Total Introduced</div>
        </div>
        <div class="evolution-stat">
            <div class="evolution-stat-value negative">-${totalFixed}</div>
            <div class="evolution-stat-label">Total Fixed</div>
        </div>
        <div class="evolution-stat">
            <div class="evolution-stat-value ${finalDebt > 0 ? 'positive' : finalDebt < 0 ? 'negative' : 'neutral'}">${finalDebt > 0 ? '+' : ''}${finalDebt}</div>
            <div class="evolution-stat-label">Net Impact</div>
        </div>
        <div class="evolution-stat" style="grid-column: 1 / -1; text-align: center; font-size: 0.85rem; padding: 0.5rem;">
            ${toolsList}
        </div>
    `;

    // Dimensions - MUCH MORE GENEROUS spacing for readability
    const padding = { top: 60, right: 40, bottom: 60, left: 60 };
    const barWidth = Math.max(8, 20 * evolutionZoom); // Wider bars
    const gap = Math.max(2, 6 * evolutionZoom); // More space
    const width = Math.max(container.clientWidth, padding.left + padding.right + commits.length * (barWidth + gap));
    const height = 400; // Taller for better visibility
    const chartHeight = height - padding.top - padding.bottom;
    
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    svg.style.width = width + 'px';

    // Scales
    // Y-scale needs to accommodate max bars (intro/fixed) and cumulative line
    const maxBar = Math.max(
        ...commits.map(c => c.introduced), 
        ...commits.map(c => c.fixed),
        10 // Minimum scale
    );
    const maxCum = Math.max(...commits.map(c => Math.abs(c.cumulative)), 10);
    // We'll use a shared scale where 1 unit of bar = 1 unit of cumulative roughly
    const maxY = Math.max(maxBar, maxCum) * 1.2;
    
    const yScale = (val) => {
        // Map 0 to center
        const center = padding.top + chartHeight / 2;
        // Scale factor: how many pixels per unit
        const scale = (chartHeight / 2) / maxY;
        return center - (val * scale);
    };
    
    const zeroY = yScale(0);

    let svgContent = '';

    // Draw Grid & Axes - CLEARER LABELING
    const yTicks = [-maxY, -maxY/2, 0, maxY/2, maxY].map(v => Math.round(v));
    yTicks.forEach(val => {
        const y = yScale(val);
        const isZero = val === 0;
        svgContent += `<line class="evo-axis-line" x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" stroke-dasharray="${isZero ? '' : '4,4'}" opacity="${isZero ? 0.5 : 0.2}"/>`;
        
        // Better labels: show absolute values, not negative numbers
        let label = '';
        if (val > 0) {
            label = `${val}`; // Issues Introduced
        } else if (val < 0) {
            label = `${Math.abs(val)}`; // Issues Fixed (show as positive)
        } else {
            label = '0';
        }
        
        svgContent += `<text class="evo-axis-label" x="${padding.left - 10}" y="${y + 3}" text-anchor="end" fill="${val > 0 ? '#ef476f' : val < 0 ? '#06d6a0' : '#a0a0c0'}">${label}</text>`;
    });
    
    // Add axis direction labels
    svgContent += `<text x="${padding.left - 45}" y="${yScale(maxY * 0.7)}" text-anchor="middle" fill="#ef476f" style="font-size: 10px; font-weight: 600;">ADDED ↑</text>`;
    svgContent += `<text x="${padding.left - 45}" y="${yScale(-maxY * 0.7)}" text-anchor="middle" fill="#06d6a0" style="font-size: 10px; font-weight: 600;">FIXED ↓</text>`;

    // Draw Tool Zones at the top - CLEANER VERSION (only show if zone is wide enough)
    let currentTool = null;
    let toolStartX = padding.left;
    const minZoneWidth = 60; // Don't label zones smaller than this
    
    commits.forEach((c, i) => {
        if (c.tool !== currentTool) {
            if (currentTool !== null) {
                const endX = padding.left + i * (barWidth + gap);
                const zoneWidth = endX - toolStartX;
                const toolColor = commits.find(cm => cm.tool === currentTool)?.colors.intro || '#a0a0c0';
                
                // Only draw if zone is wide enough
                if (zoneWidth >= minZoneWidth) {
                    svgContent += `<rect x="${toolStartX}" y="10" width="${zoneWidth}" height="12" fill="${toolColor}" opacity="0.4" rx="3"/>`;
                    svgContent += `<text x="${toolStartX + zoneWidth / 2}" y="18" text-anchor="middle" fill="#fff" style="font-size: 10px; font-weight: 600; text-transform: uppercase;">${currentTool}</text>`;
                }
            }
            currentTool = c.tool;
            toolStartX = padding.left + i * (barWidth + gap);
        }
    });
    
    // Draw last tool zone
    if (currentTool !== null) {
        const endX = padding.left + commits.length * (barWidth + gap);
        const zoneWidth = endX - toolStartX;
        const toolColor = commits.find(cm => cm.tool === currentTool)?.colors.intro || '#a0a0c0';
        if (zoneWidth >= minZoneWidth) {
            svgContent += `<rect x="${toolStartX}" y="10" width="${zoneWidth}" height="12" fill="${toolColor}" opacity="0.4" rx="3"/>`;
            svgContent += `<text x="${toolStartX + zoneWidth / 2}" y="18" text-anchor="middle" fill="#fff" style="font-size: 10px; font-weight: 600; text-transform: uppercase;">${currentTool}</text>`;
        }
    }

    // Draw Bars (Intro = Up, Fix = Down) with tool-specific colors + role indicator
    commits.forEach((c, i) => {
        const x = padding.left + i * (barWidth + gap);
        const role = (c.commit.author_role || 'unknown');
        const roleColor = role === 'sole_author' ? '#34d399' : role === 'coauthor' ? '#fb923c' : '#71717a';

        // Introduced Bar (Up) - with better visibility
        if (c.introduced > 0) {
            const h = Math.abs(yScale(c.introduced) - zeroY);
            const opacity = 0.85;
            const strokeWidth = c.impact > 10 ? 2 : 1;
            svgContent += `<rect class="evo-bar-intro" x="${x}" y="${yScale(c.introduced)}" width="${barWidth}" height="${h}" rx="1" fill="${c.colors.intro}" opacity="${opacity}" stroke="${c.colors.intro}" stroke-width="${strokeWidth}" data-index="${i}"/>`;
        }

        // Fixed Bar (Down) - with better visibility
        if (c.fixed > 0) {
            const h = Math.abs(yScale(-c.fixed) - zeroY);
            const opacity = 0.85;
            const strokeWidth = c.impact > 10 ? 2 : 1;
            svgContent += `<rect class="evo-bar-fix" x="${x}" y="${zeroY}" width="${barWidth}" height="${h}" rx="1" fill="${c.colors.fix}" opacity="${opacity}" stroke="${c.colors.fix}" stroke-width="${strokeWidth}" data-index="${i}"/>`;
        }

        // Role indicator dot below the bar area (only in "All" mode)
        if (dashboardRoleFilter === 'all') {
            svgContent += `<rect x="${x}" y="${height - padding.bottom + 8}" width="${barWidth}" height="4" rx="2" fill="${roleColor}" opacity="0.8"/>`;
        }

        // Draw subtle tool transition marker (only circle at top, no vertical line)
        if (i > 0 && c.tool !== commits[i - 1].tool) {
            svgContent += `<circle cx="${x - gap/2}" cy="${padding.top - 5}" r="3" fill="#fff" opacity="0.6" stroke="${c.colors.intro}" stroke-width="2"/>`;
        }
    });

    // Role legend at bottom (only in "All" mode)
    if (dashboardRoleFilter === 'all') {
        const legendX = width - padding.right - 220;
        const legendY = height - 12;
        svgContent += `<rect x="${legendX}" y="${legendY - 5}" width="8" height="8" rx="2" fill="#34d399"/>`;
        svgContent += `<text x="${legendX + 12}" y="${legendY + 2}" fill="#a1a1aa" style="font-size:9px;">Single-Author</text>`;
        svgContent += `<rect x="${legendX + 100}" y="${legendY - 5}" width="8" height="8" rx="2" fill="#fb923c"/>`;
        svgContent += `<text x="${legendX + 112}" y="${legendY + 2}" fill="#a1a1aa" style="font-size:9px;">Multi-Author</text>`;
    }

    // Draw Cumulative Trend Line
    let pathD = '';
    commits.forEach((c, i) => {
        const x = padding.left + i * (barWidth + gap) + barWidth / 2;
        const y = yScale(c.cumulative);
        pathD += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
    });
    
    // Explicitly set fill="none" to prevent black polygon artifact
    svgContent += `<path class="evo-trend-line" d="${pathD}" fill="none" stroke="#818cf8" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />`;

    // Draw Trend Markers
    commits.forEach((c, i) => {
        // Only show marker if significant change or milestone
        if (c.impact > 0 || i === 0 || i === commits.length - 1) {
            const x = padding.left + i * (barWidth + gap) + barWidth / 2;
            const y = yScale(c.cumulative);
            svgContent += `<circle class="evo-marker" cx="${x}" cy="${y}" r="4" fill="#18181b" stroke="#818cf8" stroke-width="2" data-index="${i}"/>`;
        }
    });

    // Labels
    svgContent += `<text class="evo-axis-label" x="${width/2}" y="${height-5}" text-anchor="middle" fill="#a0a0c0" style="font-size: 11px; font-weight: 500;">Timeline (AI Commits)</text>`;
    svgContent += `<text class="evo-axis-label" x="15" y="${height/2}" text-anchor="middle" transform="rotate(-90, 15, ${height/2})" fill="#a0a0c0" style="font-size: 11px; font-weight: 500;">Issues (Cumulative)</text>`;

    // Add Annotation for "Janitor" fixes (if we see fixes but no prior debt)
    if (finalDebt < 0 && peakDebt === 0) {
        const firstFix = commits.find(c => c.fixed > 0);
        if (firstFix) {
             const x = padding.left + firstFix.index * (barWidth + gap);
             const y = yScale(firstFix.cumulative);
             svgContent += `
                <g transform="translate(${x}, ${y + 30})">
                    <line x1="0" y1="-10" x2="0" y2="-20" stroke="#a0a0c0" stroke-dasharray="2,2"/>
                    <text x="0" y="0" text-anchor="middle" fill="#06d6a0" style="font-size: 10px;">Fixing Pre-existing Debt</text>
                </g>
             `;
        }
    }

    svg.innerHTML = svgContent;

    // Interaction
    const handleHover = (target, idx) => {
        const c = commits[idx];
        const role = c.commit.author_role || 'unknown';
        const roleBadge = role === 'sole_author'
            ? '<span style="background:rgba(52,211,153,0.2);color:#34d399;padding:2px 6px;border-radius:4px;font-size:0.75rem;margin-left:4px;">Single-Author</span>'
            : role === 'coauthor'
            ? '<span style="background:rgba(251,146,60,0.2);color:#fb923c;padding:2px 6px;border-radius:4px;font-size:0.75rem;margin-left:4px;">Multi-Author</span>'
            : '';
        tooltip.innerHTML = `
            <div class="tooltip-row header">
                <span>${c.sha}</span>
                <span style="background: ${c.colors.intro}; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem;">${c.toolDisplay}</span>${roleBadge}
            </div>
            <div class="tooltip-row">
                <span>Introduced:</span>
                <span class="tooltip-val" style="color: ${c.colors.intro}">+${c.introduced}</span>
            </div>
            <div class="tooltip-row">
                <span>Fixed:</span>
                <span class="tooltip-val" style="color: ${c.colors.fix}">-${c.fixed}</span>
            </div>
            <div class="tooltip-row" style="border-top:1px solid rgba(255,255,255,0.1); margin-top:4px; padding-top:4px;">
                <span>Net Change:</span>
                <span class="tooltip-val ${c.net > 0 ? 'pos' : c.net < 0 ? 'neg' : 'neutral'}">${c.net > 0 ? '+' : ''}${c.net}</span>
            </div>
            <div class="tooltip-row">
                <span>Cumulative:</span>
                <span class="tooltip-val neutral">${c.cumulative}</span>
            </div>
            <div class="tooltip-row" style="font-size: 0.8rem; color: #a0a0c0; margin-top: 4px;">
                <span>Commit #${idx + 1} of ${commits.length}</span>
            </div>
        `;
        tooltip.classList.add('visible');
    };

    svg.querySelectorAll('.evo-bar-intro, .evo-bar-fix, .evo-marker').forEach(el => {
        el.addEventListener('mouseenter', (e) => handleHover(e.target, parseInt(el.dataset.index)));
        el.addEventListener('mousemove', (e) => {
            // Smart positioning: avoid going off-screen
            const tooltipWidth = 220; // Approximate tooltip width
            const tooltipHeight = 150; // Approximate tooltip height
            const padding = 15;
            
            let left = e.clientX + padding;
            let top = e.clientY - tooltipHeight / 2;
            
            // If tooltip would go off right edge, position to the left of cursor
            if (left + tooltipWidth > window.innerWidth) {
                left = e.clientX - tooltipWidth - padding;
            }
            
            // If tooltip would go off bottom, move it up
            if (top + tooltipHeight > window.innerHeight) {
                top = window.innerHeight - tooltipHeight - padding;
            }
            
            // If tooltip would go off top, move it down
            if (top < 0) {
                top = padding;
            }
            
            tooltip.style.left = left + 'px';
            tooltip.style.top = top + 'px';
        });
        el.addEventListener('mouseleave', () => tooltip.classList.remove('visible'));
        el.addEventListener('click', (e) => showCommitDetails(commits[parseInt(el.dataset.index)].commit));
    });

    console.log(`[Dashboard] Evolution timeline rendered with ${commits.length} commits`);
}

function renderDebtChart() {
    const ctx = document.getElementById('debt-chart').getContext('2d');

    if (debtChartInstance) {
        debtChartInstance.destroy();
    }

    const activeData = getActiveDebtData();
    const labels = activeData.map((_, i) => `C${i + 1}`);

    // Build single cumulative line; color each dot + segment by commit's role
    let runningTotal = 0;
    const data = [];
    const pointColors = [];
    activeData.forEach(commit => {
        const counts = getCommitIssueCounts(commit);
        runningTotal += counts.introduced - counts.fixed;
        data.push(runningTotal);
        const role = commit.author_role || 'unknown';
        pointColors.push(role === 'sole_author' ? '#34d399' : role === 'coauthor' ? '#fb923c' : '#71717a');
    });

    const showRoleColors = dashboardRoleFilter === 'all';
    const singleColor = dashboardRoleFilter === 'sole_author' ? '#34d399'
                       : dashboardRoleFilter === 'coauthor' ? '#fb923c'
                       : '#818cf8';

    const dataset = {
        label: 'Cumulative Debt',
        data,
        borderColor: showRoleColors ? '#818cf880' : singleColor,
        backgroundColor: showRoleColors ? 'rgba(129,140,248,0.05)' : singleColor + '15',
        fill: true,
        tension: 0.3,
        pointBackgroundColor: showRoleColors ? pointColors : singleColor,
        pointBorderColor: '#18181b',
        pointBorderWidth: 1,
        pointRadius: showRoleColors ? 3.5 : 3,
        borderWidth: 2,
    };

    // Color line segments by the role of the starting commit (Chart.js 3+ segment API)
    if (showRoleColors) {
        dataset.segment = {
            borderColor: function(ctx) {
                const role = activeData[ctx.p0DataIndex]?.author_role || 'unknown';
                return role === 'sole_author' ? '#34d399' : role === 'coauthor' ? '#fb923c' : '#71717a';
            }
        };
    }

    debtChartInstance = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets: [dataset] },
        options: {
            responsive: true,
            plugins: {
                legend: showRoleColors ? {
                    labels: {
                        generateLabels: () => [
                            { text: 'Single-Author', fillStyle: '#34d399', strokeStyle: '#34d399', lineWidth: 2, pointStyle: 'circle' },
                            { text: 'Multi-Author', fillStyle: '#fb923c', strokeStyle: '#fb923c', lineWidth: 2, pointStyle: 'circle' },
                        ]
                    }
                } : { display: false },
                tooltip: {
                    callbacks: {
                        afterLabel: function(ctx) {
                            const commit = activeData[ctx.dataIndex];
                            if (!commit) return '';
                            const role = commit.author_role || 'unknown';
                            return role === 'sole_author' ? '(Single-Author)' : role === 'coauthor' ? '(Multi-Author)' : '';
                        }
                    }
                }
            },
            scales: {
                y: { grid: { color: 'rgba(63,63,70,0.3)' }, ticks: { color: '#a1a1aa' } },
                x: { grid: { display: false }, ticks: { color: '#71717a' } }
            }
        }
    });
}

function renderToolChart() {
    const ctx = document.getElementById('tool-chart').getContext('2d');

    if (toolChartInstance) {
        toolChartInstance.destroy();
    }

    // Calculate per-tool stats from debt data (respects severity + role filter)
    const toolData = {};
    const toolSoleIssues = {};
    const toolCoIssues = {};
    getActiveDebtData().forEach(commit => {
        const tool = commit.ai_tool || 'unknown';
        if (!toolData[tool]) {
            toolData[tool] = { commits: 0, issues_introduced: 0 };
            toolSoleIssues[tool] = 0;
            toolCoIssues[tool] = 0;
        }
        const counts = getCommitIssueCounts(commit);
        toolData[tool].commits++;
        toolData[tool].issues_introduced += counts.introduced;
        const role = commit.author_role || 'unknown';
        if (role === 'sole_author') toolSoleIssues[tool] += counts.introduced;
        else toolCoIssues[tool] += counts.introduced;
    });

    const tools = Object.keys(toolData);
    const commits = tools.map(t => toolData[t].commits || 0);

    const colors = {
        'claude': '#a78bfa', 'copilot': '#34d399', 'cursor': '#818cf8',
        'gemini': '#fbbf24', 'coderabbit': '#38bdf8', 'unknown': '#71717a',
    };
    const bgColors = tools.map(t => colors[t.toLowerCase()] || colors['unknown']);

    // Build datasets: Commits + Issues (split by role in "All" mode)
    const datasets = [
        {
            label: 'Commits',
            data: commits,
            backgroundColor: bgColors.map(c => c + 'bb'),
            borderColor: bgColors,
            borderWidth: 1,
        },
    ];
    if (dashboardRoleFilter === 'all') {
        // Two separate issue bars (grouped, not stacked) so you can compare
        datasets.push(
            { label: 'Issues (Single-Author)', data: tools.map(t => toolSoleIssues[t] || 0), backgroundColor: 'rgba(52,211,153,0.65)', borderColor: '#34d399', borderWidth: 1 },
            { label: 'Issues (Multi-Author)', data: tools.map(t => toolCoIssues[t] || 0), backgroundColor: 'rgba(251,146,60,0.65)', borderColor: '#fb923c', borderWidth: 1 },
        );
    } else {
        const roleColor = dashboardRoleFilter === 'sole_author' ? 'rgba(52,211,153,0.6)' : 'rgba(251,146,60,0.6)';
        datasets.push({
            label: 'Issues',
            data: tools.map(t => toolData[t].issues_introduced || 0),
            backgroundColor: roleColor,
            borderColor: roleColor.replace('0.6)', '1)'),
            borderWidth: 1,
        });
    }

    toolChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: tools.map(t => t.charAt(0).toUpperCase() + t.slice(1)), datasets },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top', labels: { color: '#a1a1aa' } } },
            scales: {
                y: { grid: { color: 'rgba(63,63,70,0.3)' }, ticks: { color: '#a1a1aa' } },
                x: { grid: { display: false }, ticks: { color: '#a1a1aa' } }
            }
        }
    });
}

function renderValuationChart() {
    const ctx = document.getElementById('valuation-chart').getContext('2d');

    // Destroy previous instance
    if (valuationChartInstance) {
        valuationChartInstance.destroy();
    }

    const valuations = { HIGH: 0, MEDIUM: 0, LOW: 0 };
    destinyData.forEach(d => {
        const val = d.developer_valuation || 'LOW';
        valuations[val]++;
    });

    valuationChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['HIGH', 'MEDIUM', 'LOW'],
            datasets: [{
                label: 'Commits',
                data: Object.values(valuations),
                backgroundColor: ['rgba(52,211,153,0.75)', 'rgba(251,191,36,0.75)', 'rgba(248,113,113,0.75)'],
                borderColor: ['#34d399', '#fbbf24', '#f87171'],
                borderWidth: 1,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                y: { grid: { color: 'rgba(63,63,70,0.3)' }, ticks: { color: '#a1a1aa' } },
                x: { grid: { display: false }, ticks: { color: '#a1a1aa' } }
            }
        }
    });
}

let timelineChartInstance = null;

function renderTimelineChart() {
    const ctx = document.getElementById('timeline-chart');
    const summaryEl = document.getElementById('lifecycle-summary-stats');
    if (!ctx) return;

    // Aggregate all files across all lifecycle commits
    const fileMap = new Map(); // filepath -> aggregated stats
    let totalSurvived = 0, totalModified = 0, totalDeleted = 0;
    let totalFixed = 0, totalRefactored = 0;

    lifecycleData.forEach(commit => {
        (commit.files || []).forEach(f => {
            const path = f.filepath || '';
            if (!path) return;

            const existing = fileMap.get(path) || {
                filepath: path,
                status: f.status || 'SURVIVED',
                num_changes: 0,
                was_fixed: false,
                was_refactored: false,
                days_to_first_change: null,
                commit_count: 0,
            };
            existing.num_changes += (f.num_changes || 0);
            existing.commit_count += 1;
            if (f.was_fixed) existing.was_fixed = true;
            if (f.was_refactored) existing.was_refactored = true;
            // Keep the worst status
            if (f.status === 'DELETED') existing.status = 'DELETED';
            else if (f.status === 'MODIFIED' && existing.status !== 'DELETED') existing.status = 'MODIFIED';
            if (f.days_to_first_change && (!existing.days_to_first_change || f.days_to_first_change < existing.days_to_first_change)) {
                existing.days_to_first_change = f.days_to_first_change;
            }
            fileMap.set(path, existing);
        });
    });

    const allFiles = Array.from(fileMap.values());
    allFiles.forEach(f => {
        if (f.status === 'SURVIVED') totalSurvived++;
        else if (f.status === 'MODIFIED') totalModified++;
        else if (f.status === 'DELETED') totalDeleted++;
        if (f.was_fixed) totalFixed++;
        if (f.was_refactored) totalRefactored++;
    });

    // Render lifecycle summary cards
    if (summaryEl) {
        const total = allFiles.length;
        summaryEl.innerHTML = total === 0 ? '' : `
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value" style="font-size:1.3rem;">${total}</div>
                <div class="card-label">Files Tracked</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value positive" style="font-size:1.3rem;">${totalSurvived}</div>
                <div class="card-label">Survived</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value warning" style="font-size:1.3rem;">${totalModified}</div>
                <div class="card-label">Modified</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value negative" style="font-size:1.3rem;">${totalDeleted}</div>
                <div class="card-label">Deleted</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value" style="font-size:1.3rem;">${totalFixed}</div>
                <div class="card-label">Had Fixes</div>
            </div>
            <div class="card survival-card" style="padding:0.75rem;">
                <div class="card-value" style="font-size:1.3rem;">${totalRefactored}</div>
                <div class="card-label">Refactored</div>
            </div>
        `;
    }

    if (allFiles.length === 0) return;

    // Show top 30 most-changed files in the chart
    const topFiles = allFiles
        .filter(f => f.num_changes > 0 || f.status === 'DELETED')
        .sort((a, b) => b.num_changes - a.num_changes)
        .slice(0, 30);

    if (topFiles.length === 0) {
        // All files are stable with 0 changes -- show top by commit count
        topFiles.push(...allFiles.sort((a, b) => b.commit_count - a.commit_count).slice(0, 15));
    }

    const labels = topFiles.map(f => {
        const name = f.filepath.split('/').pop();
        return name.length > 30 ? name.substring(0, 27) + '...' : name;
    });
    const numChanges = topFiles.map(f => f.num_changes);
    const statusColors = topFiles.map(f => {
        if (f.status === 'SURVIVED') return '#34d399';
        if (f.status === 'MODIFIED') return '#fbbf24';
        if (f.status === 'DELETED') return '#f87171';
        return '#818cf8';
    });

    // Destroy previous chart
    if (timelineChartInstance) {
        timelineChartInstance.destroy();
    }

    timelineChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Subsequent Changes',
                data: numChanges,
                backgroundColor: statusColors,
                borderRadius: 4,
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: function(context) {
                            return topFiles[context[0].dataIndex].filepath;
                        },
                        label: function(context) {
                            const f = topFiles[context.dataIndex];
                            return `${f.status}: ${f.num_changes} changes across ${f.commit_count} commit(s)`;
                        },
                        afterLabel: function(context) {
                            const f = topFiles[context.dataIndex];
                            const extras = [];
                            if (f.was_fixed) extras.push('Had fixes');
                            if (f.was_refactored) extras.push('Was refactored');
                            if (f.days_to_first_change) extras.push(`First change: ${f.days_to_first_change.toFixed(1)} days`);
                            return extras.length ? extras.join(' | ') : '';
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(63,63,70,0.3)' },
                    ticks: { color: '#a1a1aa' },
                    title: { display: true, text: 'Total Subsequent Changes', color: '#a1a1aa' }
                },
                y: {
                    grid: { display: false },
                    ticks: { color: '#a1a1aa', font: { size: 11 } }
                }
            }
        }
    });
}

// Keep for backward compatibility (no longer needs dropdown)
function updateTimelineChart() {
    renderTimelineChart();
}
