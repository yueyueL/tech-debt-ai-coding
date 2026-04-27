function resolveDatasetName(defaultName = 'out') {
    const raw = new URLSearchParams(window.location.search).get('dataset') || defaultName;
    return /^[A-Za-z0-9._-]+$/.test(raw) ? raw : defaultName;
}

const FALSE_POSITIVE_DATASET = resolveDatasetName();

function datasetQuery() {
    return FALSE_POSITIVE_DATASET === 'out'
        ? ''
        : `?dataset=${encodeURIComponent(FALSE_POSITIVE_DATASET)}`;
}

function appendDatasetToHref(href) {
    if (!href || href.includes('dataset=')) return href;
    const datasetParam = `dataset=${encodeURIComponent(FALSE_POSITIVE_DATASET)}`;
    return href.includes('?') ? `${href}&${datasetParam}` : `${href}?${datasetParam}`;
}

function applyDatasetLinks() {
    document.querySelectorAll('[data-preserve-dataset="true"]').forEach(anchor => {
        const href = anchor.getAttribute('href');
        if (!href || href.startsWith('#') || FALSE_POSITIVE_DATASET === 'out') return;
        anchor.setAttribute('href', appendDatasetToHref(href));
    });
}

async function loadAggregate() {
    const candidates = [
        `/results/${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `../../results/${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `../results/${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `results/${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `/${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `../../${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `../${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
        `${FALSE_POSITIVE_DATASET}/aggregate_summary.json`,
    ];
    for (const path of candidates) {
        try {
            const response = await fetch(path);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.debug('[FalsePositives] failed to load', path, error);
        }
    }
    return null;
}

function renderSummary(summary) {
    const grid = document.getElementById('summary-grid');
    grid.innerHTML = [
        ['Total Issues', summary.total_issues || 0],
        ['Likely False Positive', summary.likely_false_positive || 0],
        ['Low Signal', summary.low_signal || 0],
        ['Visible by Default', summary.visible_by_default || 0],
    ].map(([label, value]) => `
        <div class="mini-stat">
            <div class="mini-stat-value">${Number(value || 0).toLocaleString()}</div>
            <div class="mini-stat-label">${label}</div>
        </div>
    `).join('');
}

function renderPatterns(patterns) {
    const list = document.getElementById('pattern-list');
    if (!patterns.length) {
        list.innerHTML = '<div class="empty-state">No pattern summary available.</div>';
        return;
    }

    list.innerHTML = patterns.map(pattern => `
        <div class="pattern-card">
            <div class="pattern-meta"><span class="chip fp">${pattern.category || 'likely_false_positive'}</span> ${Number(pattern.count || 0).toLocaleString()} issues · ${pattern.share_pct || 0}% of total</div>
            <h3>${pattern.label || pattern.id}</h3>
            <p>${pattern.description || ''}</p>
            <div class="pattern-meta">Top rules</div>
            <ul class="rule-list">
                ${(pattern.top_rules || []).map(rule => `<li><code>${rule.name}</code> · ${Number(rule.count || 0).toLocaleString()}</li>`).join('')}
            </ul>
            <div class="pattern-meta">Sample paths</div>
            <ul class="path-list">
                ${(pattern.sample_paths || []).map(path => `<li><code>${path}</code></li>`).join('')}
            </ul>
        </div>
    `).join('');
}

function renderLowSignal(rules) {
    const list = document.getElementById('low-signal-list');
    if (!rules.length) {
        list.innerHTML = '<div class="empty-state">No low-signal rule summary available.</div>';
        return;
    }

    list.innerHTML = rules.map(rule => `
        <div class="pattern-card">
            <div class="pattern-meta"><span class="chip low">low signal</span> ${Number(rule.count || 0).toLocaleString()} issues · ${rule.share_pct || 0}% of total</div>
            <h3><code>${rule.name}</code></h3>
            <div class="pattern-meta">Sample paths</div>
            <ul class="path-list">
                ${(rule.sample_paths || []).map(path => `<li><code>${path}</code></li>`).join('')}
            </ul>
        </div>
    `).join('');
}

document.addEventListener('DOMContentLoaded', async () => {
    applyDatasetLinks();
    const data = await loadAggregate();
    if (!data || !data.false_positive_patterns) {
        document.getElementById('loading-msg').textContent = 'No false-positive summary found. Regenerate aggregate_summary.json first.';
        return;
    }

    document.getElementById('loading-msg').style.display = 'none';
    document.getElementById('content').style.display = 'block';
    renderSummary(data.false_positive_patterns.summary || {});
    renderPatterns(data.false_positive_patterns.patterns || []);
    renderLowSignal(data.false_positive_patterns.low_signal_rules || []);
});
