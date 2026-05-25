
(function () {
  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.add('oh-motion-ready');

  if (reduceMotion) return;

  const revealSelectors = [
    'nav',
    'main > *',
    'main section',
    '.page-head',
    '.section-intro',
    '.feature-grid > *',
    '.preview-grid > *',
    '.pricing-grid > *',
    '.servers-grid > *',
    '.stats-grid > *',
    '.tool-grid > *',
    'form > *',
    'footer',
    'h1',
    'h2',
    'p'
  ];

  const seen = new Set();
  let revealIndex = 0;

  function addReveal(el, baseDelay = 35) {
    if (!el || seen.has(el) || el.closest('script, style')) return;
    seen.add(el);
    el.classList.add('oh-reveal');
    el.style.setProperty('--oh-delay', `${Math.min(revealIndex * baseDelay, 520)}ms`);
    revealIndex += 1;
  }

  revealSelectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(el => addReveal(el));
  });

  const cardSelectors = [
    '.hero-copy',
    '.surface-card',
    '.feature-card',
    '.preview-card',
    '.server-card',
    '.plan-card',
    '.panel',
    '.stat-card',
    '.plan-sidebar',
    '.auth-card',
    '.auth-panel',
    '.message-card',
    '.upload-box',
    '.empty-state',
    '.comparison-table',
    '.note-card'
  ];

  const cards = new Set();
  cardSelectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(el => {
      if (el.matches('input, button, a, nav') || el.closest('nav')) return;
      if (el.children.length === 0 && (el.textContent || '').trim().length < 24) return;
      cards.add(el);
    });
  });

  let cardIndex = 0;
  cards.forEach(el => {
    el.classList.add('oh-card-motion');
    if (!el.classList.contains('oh-reveal')) {
      el.classList.add('oh-soft-scale');
      el.style.setProperty('--oh-delay', `${Math.min(cardIndex * 45 + 80, 620)}ms`);
    }
    cardIndex += 1;
  });

  document.querySelectorAll('button, a, input, textarea, select').forEach(el => {
    el.classList.add('oh-interactive');
  });

  document.querySelectorAll('nav a').forEach(el => {
    el.classList.add('oh-nav-link');
  });

  document.querySelectorAll('span, div').forEach(el => {
    const text = (el.textContent || '').trim().toLowerCase();
    if (['online', 'active', 'starting', 'running'].includes(text)) {
      el.classList.add('oh-status-pulse');
    }
  });

  const consoleCandidates = Array.from(document.querySelectorAll('div'))
    .filter(el => /\[\d{2}:\d{2}:\d{2}\]/.test(el.textContent || ''));
  consoleCandidates.forEach((el, index) => {
    el.classList.add('oh-console-line');
    el.style.setProperty('--oh-delay', `${Math.min(index * 55, 900)}ms`);
  });

  document.querySelectorAll('input[placeholder*="command" i], input[placeholder*="send" i]').forEach(input => {
    const previous = input.previousElementSibling;
    if (previous) previous.classList.add('oh-terminal-cursor');
  });

  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || href === '#' || href.startsWith('http') || href.startsWith('mailto:') || href.startsWith('#')) return;
    event.preventDefault();
    document.body.classList.add('oh-page-exit');
    window.setTimeout(() => { window.location.href = href; }, 150);
  });
})();
