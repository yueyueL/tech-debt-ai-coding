/**
 * AI Code Analysis Dashboard — Data Loading & Initialization
 * Repo scanning, dropdown, data fetching, and DOMContentLoaded entry point.
 */

function resolveDatasetName(defaultName = 'out') {
    const raw = new URLSearchParams(window.location.search).get('dataset') || defaultName;
    return /^[A-Za-z0-9._-]+$/.test(raw) ? raw : defaultName;
}

const DATASET_NAME = resolveDatasetName();

function buildDatasetQuery(extra = '') {
    if (DATASET_NAME === 'out') return extra ? `?${extra}` : '';
    const datasetParam = `dataset=${encodeURIComponent(DATASET_NAME)}`;
    return extra ? `?${extra}&${datasetParam}` : `?${datasetParam}`;
}

function appendDatasetToHref(href) {
    if (!href || href.includes('dataset=')) return href;
    const datasetParam = `dataset=${encodeURIComponent(DATASET_NAME)}`;
    return href.includes('?') ? `${href}&${datasetParam}` : `${href}?${datasetParam}`;
}

function getDatasetBasePaths() {
    // Reproduction-package convention: data lives under results/<DATASET_NAME>/.
    // Try those locations first, then fall back to legacy top-level locations
    // for backward compatibility with older runs.
    return [
        `/results/${DATASET_NAME}`,
        `../../results/${DATASET_NAME}`,
        `../results/${DATASET_NAME}`,
        `./results/${DATASET_NAME}`,
        `results/${DATASET_NAME}`,
        `/${DATASET_NAME}`,
        `../../${DATASET_NAME}`,
        `../${DATASET_NAME}`,
        `./${DATASET_NAME}`,
        DATASET_NAME,
    ];
}

function applyDatasetLinks() {
    document.querySelectorAll('[data-preserve-dataset="true"]').forEach(anchor => {
        const href = anchor.getAttribute('href');
        if (!href || href.startsWith('#') || DATASET_NAME === 'out') return;
        anchor.setAttribute('href', appendDatasetToHref(href));
    });
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    initUIEnhancements();
    applyDatasetLinks();
    await scanForRepos();
    setupRepoFilter();
    populateRepoDropdown();
    await loadRepoData(currentRepoPath);
    renderSummaryCards();
    renderCharts();
    renderTables();
    setupModal();
    document.getElementById('last-updated').textContent = new Date().toLocaleString();
    // Re-trigger scroll reveal after content loads (sections may now be visible)
    initScrollReveal();
});

/**
 * Populate the repo dropdown with available repos
 */
function populateRepoDropdown() {
    const select = document.getElementById('repo-select');
    select.innerHTML = '';

    if (availableRepos.length === 0) {
        select.innerHTML = '<option value="">No repos found - run pipeline first</option>';
        console.warn('[Dashboard] No repos available. Run: python scripts/run_pipeline.py --input <commits.json>');
        return;
    }

    const filtered = getFilteredRepos();

    if (filtered.length === 0) {
        select.innerHTML = '<option value="">No matching repos</option>';
        return;
    }

    const query = (repoFilter || '').trim();
    if (query) {
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = `(${filtered.length} match${filtered.length === 1 ? '' : 'es'}) select repo…`;
        select.appendChild(placeholder);
    }

    filtered.forEach(repo => {
        const option = document.createElement('option');
        option.value = repo.path;
        // Format repo name for display (replace underscores with /)
        option.textContent = repo.displayName;
        if (repo.path === currentRepoPath) {
            option.selected = true;
        }
        select.appendChild(option);
    });

    // If filtering hides the currently selected repo, keep the dropdown on the placeholder
    // instead of implicitly selecting the first match (which does not load data).
    if (query && !filtered.some(r => r.path === currentRepoPath)) {
        select.value = '';
    }

    console.log(`[Dashboard] Populated dropdown with ${availableRepos.length} repos`);
}

/**
 * Switch to a different repo and reload all data
 */
async function switchRepo(repoPath) {
    if (!repoPath || repoPath === currentRepoPath) return;

    const loadSeq = ++repoLoadSeq;
    currentRepoPath = repoPath;
    debugData = {};  // Clear debug cache
    resetRuleSeverityCache();  // Reset rule severity mapping for new repo
    dashboardRoleFilter = 'all';  // Reset role filter for new repo
    document.querySelectorAll('.role-filter-dash-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.drole === 'all')
    );

    await loadRepoData(repoPath, loadSeq);
    if (loadSeq !== repoLoadSeq) return; // A newer repo switch won the race
    renderSummaryCards();
    renderCharts();
    renderTables();
    document.getElementById('last-updated').textContent = new Date().toLocaleString();
    // Re-init scroll reveal for newly-visible sections
    initScrollReveal();
}

function setupRepoFilter() {
    const input = document.getElementById('repo-search');
    if (!input) return;
    input.addEventListener('input', () => {
        repoFilter = input.value || '';
        populateRepoDropdown();
        const filtered = getFilteredRepos();
        // Only auto-switch when the filter uniquely identifies a single repo.
        if (filtered.length === 1 && filtered[0].path !== currentRepoPath) {
            const select = document.getElementById('repo-select');
            if (select) select.value = filtered[0].path;
            switchRepo(filtered[0].path);
        }
    });
    input.addEventListener('keydown', (e) => {
        if (e.key !== 'Enter') return;
        const filtered = getFilteredRepos();
        if (filtered.length > 0) {
            const select = document.getElementById('repo-select');
            if (select) select.value = filtered[0].path;
            switchRepo(filtered[0].path);
        }
    });
}


/**
 * Scan for available repos (subfolders with debt_metrics.json)
 */
async function scanForRepos() {
    // Try multiple possible paths depending on how the dashboard is served
    // - /out (absolute from server root)
    // - ../../out (relative from src/ui/)
    // - ../out, ./out, out (other relative paths)
    const basePaths = getDatasetBasePaths();

    // Check URL params for specific repo first
    const urlParams = new URLSearchParams(window.location.search);
    const repoName = urlParams.get('repo');

    console.log(`[Dashboard] Scanning ${DATASET_NAME} repos in paths:`, basePaths);
    
    for (const base of basePaths) {
        console.debug(`[Dashboard] Trying base path: ${base}`);
        
        // If specific repo requested via URL param
        if (repoName) {
            const targetPath = `${base}/${repoName}`;
            const debt = await fetchJSON(`${targetPath}/debt_metrics.json`);
            if (debt.length > 0) {
                console.log(`[Dashboard] Found repo via URL param: ${targetPath}`);
                currentRepoPath = targetPath;
            const displayName = formatRepoName(repoName);
            availableRepos = [{
                name: repoName,
                path: targetPath,
                displayName,
                displayNameLower: displayName.toLowerCase(),
            }];
            return;
        }
        }

        // Try legacy flat structure first
        const legacyDebt = await fetchJSON(`${base}/debt_metrics.json`);
        if (legacyDebt.length > 0) {
            console.log(`[Dashboard] Found legacy flat structure at: ${base}`);
            const displayName = 'default';
            availableRepos = [{
                name: 'default',
                path: base,
                displayName,
                displayNameLower: displayName.toLowerCase(),
            }];
            currentRepoPath = base;
            return;
        }

        // Try to find any subfolder with debt_metrics.json
        // Read repos.json manifest if available
        const reposList = await fetchJSON(`${base}/repos.json`);
        console.debug(`[Dashboard] repos.json at ${base}:`, reposList);
        
        const commonRepos = Array.isArray(reposList) && reposList.length > 0
            ? reposList
            : [];  // Don't use hardcoded fallbacks

        for (const repo of commonRepos) {
            const repoPath = `${base}/${repo}`;
            const debt = await fetchJSON(`${repoPath}/debt_metrics.json`);
            if (debt.length > 0) {
                console.log(`[Dashboard] Found repo: ${repo} at ${repoPath}`);
                const displayName = formatRepoName(repo);
                availableRepos.push({
                    name: repo,
                    path: repoPath,
                    displayName,
                    displayNameLower: displayName.toLowerCase(),
                });
                if (!currentRepoPath) {
                    currentRepoPath = repoPath;
                }
            }
        }

        if (currentRepoPath) {
            console.log(`[Dashboard] Using repo path: ${currentRepoPath}`);
            return;
        }
    }
    
    console.warn('[Dashboard] No repos found in any path');
}

/**
 * Load all JSON data files for a specific repo
 */
async function loadRepoData(basePath, loadSeq = null) {
    try {
        const [debt, lifecycle, destiny, summary, deepScan, deepScanCommits, issueSurvival] = await Promise.all([
            fetchJSON(`${basePath}/debt_metrics.json`),
            fetchJSON(`${basePath}/lifecycle_metrics.json`),
            fetchJSON(`${basePath}/destiny_metrics.json`),
            fetchJSON(`${basePath}/research_summary.json`),
            fetchJSON(`${basePath}/deep_scan_results.json`),
            fetchJSON(`${basePath}/deep_scan_commits.json`),
            fetchJSON(`${basePath}/issue_survival.json`),
        ]);

        if (loadSeq !== null && loadSeq !== repoLoadSeq) return;

        // Filter out tainted commits caused by the shallow-clone parent-resolution
        // fallback. When get_commit_parent() cannot resolve the parent SHA, the
        // pipeline falls back to `git diff-tree --root`, which lists the ENTIRE
        // repository tree as "Added". This inflates issue counts by attributing
        // pre-existing issues in hundreds of unrelated files to one commit.
        //
        // Fingerprint: files_total > 200 AND every file has status "A" (Added).
        const rawDebt = debt || [];
        const tainted = rawDebt.filter(c => {
            const filesTotal = c.analysis_counters?.files_total ?? 0;
            const files = c.files ?? [];
            return filesTotal > 200 && files.length > 0 && files.every(f => f.status === 'A');
        });
        if (tainted.length > 0) {
            console.warn(
                `[Dashboard] Excluded ${tainted.length} tainted commit(s) ` +
                `(shallow-clone parent-resolution fallback inflated issue counts):`,
                tainted.map(c => c.commit_hash?.substring(0, 12))
            );
        }
        debtData = rawDebt.filter(c => {
            const filesTotal = c.analysis_counters?.files_total ?? 0;
            const files = c.files ?? [];
            return !(filesTotal > 200 && files.length > 0 && files.every(f => f.status === 'A'));
        });
        lifecycleData = lifecycle || [];
        destinyData = destiny || [];
        researchSummary = summary || {};
        deepScanData = deepScan || {};
        deepScanCommitsData = deepScanCommits || {};
        issueSurvivalData = issueSurvival || {};

        // Load debug data for each commit
        await loadDebugData(basePath, loadSeq);
        if (loadSeq !== null && loadSeq !== repoLoadSeq) return;

        // Update page title with repo name
        const repoName = basePath.split('/').pop();
        if (repoName && repoName !== 'out') {
            document.querySelector('h1').textContent = `🔬 AI Code Analysis: ${repoName}`;
        }
    } catch (error) {
        console.error('Error loading data:', error);
    }
}

async function loadDebugData(basePath, loadSeq = null) {
    // Load debug files for each commit
    for (const commit of debtData) {
        if (loadSeq !== null && loadSeq !== repoLoadSeq) return;
        const fullSha = commit.commit_hash || '';
        const sha12 = fullSha.substring(0, 12);
        const sha8 = fullSha.substring(0, 8);
        const tool = (commit.ai_tool || '').trim();
        const candidates = [];

        if (sha8 && tool) candidates.push(`${basePath}/debug/${sha8}_${tool}.json`);
        if (sha12 && tool && sha12 !== sha8) candidates.push(`${basePath}/debug/${sha12}_${tool}.json`);
        if (sha8) candidates.push(`${basePath}/debug/${sha8}.json`);
        if (sha12 && sha12 !== sha8) candidates.push(`${basePath}/debug/${sha12}.json`);

        for (const path of candidates) {
            const debug = await fetchJSON(path);
            if (debug && !Array.isArray(debug) && Object.keys(debug).length > 0) {
                if (sha8) debugData[sha8] = debug;
                if (sha12) debugData[sha12] = debug;
                break;
            }
        }
    }
}

async function fetchJSON(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            console.debug(`[Dashboard] Failed to fetch ${url}: ${response.status}`);
            return [];
        }
        const data = await response.json();
        console.debug(`[Dashboard] Loaded ${url}:`, Array.isArray(data) ? `${data.length} items` : 'object');
        return data;
    } catch (err) {
        console.debug(`[Dashboard] Error fetching ${url}:`, err.message);
        return [];
    }
}
