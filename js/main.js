// Nav shadow on scroll
const nav = document.querySelector('nav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.style.boxShadow = window.scrollY > 10 ? '0 4px 40px rgba(0,0,0,0.7)' : 'none';
  });
}

// Mark active nav link based on current page
const currentPage = location.pathname.split('/').pop() || 'index.html';
document.querySelectorAll('.nav-links a, .mobile-nav a').forEach(a => {
  a.classList.remove('active');
  const href = a.getAttribute('href');
  if (href === currentPage || (currentPage === '' && href === 'index.html')) {
    a.classList.add('active');
  }
});

// Smooth scroll for anchor links (skip bare # links used for modals)
document.querySelectorAll('a[href^="#"]').forEach(a => {
  const href = a.getAttribute('href');
  if (!href || href === '#') return;
  a.addEventListener('click', e => {
    try {
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    } catch (_) {}
  });
});

// ── SCROLLING ROWS — lazy load + pause when off-screen ──
// Covers .gif-row, .img-row, .friends-img-row on all pages
(function() {
  const rows = document.querySelectorAll('.gif-row, .img-row, .friends-img-row');
  if (!rows.length || !('IntersectionObserver' in window)) return;

  // For non-gif rows: add decoding async + loading lazy
  rows.forEach(row => {
    row.querySelectorAll('img').forEach(img => {
      img.decoding = 'async';
      if (!img.getAttribute('loading') && !img.dataset.src) img.loading = 'lazy';
    });
  });

  // Track which rows have had their data-src images loaded
  const loaded = new WeakSet();

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      const row = entry.target;
      if (entry.isIntersecting) {
        // Swap data-src → src for GIF lazy loading (only once)
        if (!loaded.has(row)) {
          loaded.add(row);
          row.querySelectorAll('img[data-src]').forEach(img => {
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
          });
        }
        row.style.animationPlayState = 'running';
      } else {
        row.style.animationPlayState = 'paused';
      }
    });
  }, { rootMargin: '0px 0px 300px 0px' }); // pre-load 300px before reaching view

  rows.forEach(row => {
    row.style.animationPlayState = 'paused';
    observer.observe(row);
  });
})();


// ── MOBILE NAV ──
const hamburger = document.querySelector('.hamburger');
const mobileNav = document.querySelector('.mobile-nav');

if (hamburger && mobileNav) {
  hamburger.addEventListener('click', () => {
    const isOpen = mobileNav.classList.toggle('open');
    hamburger.classList.toggle('open', isOpen);
    document.body.style.overflow = isOpen ? 'hidden' : '';
  });

  // Close when any link is tapped
  mobileNav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      mobileNav.classList.remove('open');
      hamburger.classList.remove('open');
      document.body.style.overflow = '';
    });
  });

  // Close on outside tap
  document.addEventListener('click', e => {
    if (mobileNav.classList.contains('open') && !nav.contains(e.target) && !mobileNav.contains(e.target)) {
      mobileNav.classList.remove('open');
      hamburger.classList.remove('open');
      document.body.style.overflow = '';
    }
  });
}
