/**
 * AI Code Analysis Dashboard — UI Enhancements
 * Scroll reveal, sticky nav, scroll-to-top, active nav tracking, Chart.js defaults, animateValue.
 */

/**
 * Initialize all UI enhancements after DOM is ready
 */
function initUIEnhancements() {
    initScrollReveal();
    initStickyNav();
    initScrollToTop();
    initActiveNavTracking();
    updateChartDefaults();
}

/**
 * Intersection Observer for scroll-reveal animations
 */
function initScrollReveal() {
    const revealElements = document.querySelectorAll('.reveal');
    if (revealElements.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.08, rootMargin: '0px 0px -40px 0px' });

    revealElements.forEach(el => observer.observe(el));
}

/**
 * Sticky nav shadow on scroll
 */
function initStickyNav() {
    const nav = document.getElementById('top-nav');
    if (!nav) return;

    const onScroll = () => {
        nav.classList.toggle('scrolled', window.scrollY > 10);
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
}

/**
 * Scroll-to-top button visibility
 */
function initScrollToTop() {
    const btn = document.getElementById('scroll-top');
    if (!btn) return;

    window.addEventListener('scroll', () => {
        btn.classList.toggle('visible', window.scrollY > 500);
    }, { passive: true });

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

/**
 * Highlight active nav link based on scroll position
 */
function initActiveNavTracking() {
    const navLinks = document.querySelectorAll('.nav-link');
    const sections = [];

    navLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && href.startsWith('#')) {
            const section = document.getElementById(href.substring(1));
            if (section) sections.push({ link, section });
        }
    });

    if (sections.length === 0) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            const match = sections.find(s => s.section === entry.target);
            if (match) {
                if (entry.isIntersecting) {
                    navLinks.forEach(l => l.classList.remove('active'));
                    match.link.classList.add('active');
                }
            }
        });
    }, { threshold: 0.15, rootMargin: '-80px 0px -60% 0px' });

    sections.forEach(({ section }) => observer.observe(section));
}

/**
 * Update Chart.js defaults for the new theme
 */
function updateChartDefaults() {
    if (typeof Chart === 'undefined') return;

    Chart.defaults.color = '#a1a1aa';
    Chart.defaults.borderColor = 'rgba(63,63,70,0.3)';
    Chart.defaults.font.family = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
    Chart.defaults.plugins.legend.labels.padding = 16;
    Chart.defaults.plugins.tooltip.backgroundColor = '#1f1f23';
    Chart.defaults.plugins.tooltip.borderColor = 'rgba(129,140,248,0.3)';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.titleFont = { weight: '600' };
    Chart.defaults.elements.bar.borderRadius = 4;
    Chart.defaults.elements.line.borderWidth = 2;
    Chart.defaults.elements.point.radius = 3;
    Chart.defaults.elements.point.hoverRadius = 5;
}

/**
 * Animate a numeric value with a counting effect
 */
function animateValue(element, endValue, suffix = '', duration = 600) {
    if (!element) return;

    // Parse end value
    const isPercent = suffix === '%' || endValue.toString().includes('%');
    const isPlus = endValue.toString().startsWith('+');
    const numStr = endValue.toString().replace(/[+%]/g, '');
    const end = parseFloat(numStr);

    if (isNaN(end)) {
        element.textContent = endValue;
        return;
    }

    const start = 0;
    const startTime = performance.now();
    const isFloat = numStr.includes('.');
    const decimals = isFloat ? (numStr.split('.')[1] || '').length : 0;

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = start + (end - start) * eased;

        let display = isFloat ? current.toFixed(decimals) : Math.round(current);
        if (isPlus && display > 0) display = '+' + display;
        element.textContent = display + (isPercent ? '%' : suffix);

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}
