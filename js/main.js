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

// ── RC AUDIO SYSTEM (homepage only) ──
(function() {
  const VOL_KEY  = 'rc_volume';
  const isRoot   = location.pathname === '/' || location.pathname.match(/^\/(index\.html)?$/);

  // Only inject controls and music on homepage
  if (!isRoot) return;

  let music      = null;
  let muted      = false;
  let currentVol = parseFloat(sessionStorage.getItem(VOL_KEY) || '0.1');

  // ── Desktop volume control ──
  const navCta = document.querySelector('.nav-cta');
  const ctrl = document.createElement('div');
  ctrl.id = 'rc-vol-ctrl';
  ctrl.innerHTML = `<button id="rc-vol-btn" title="Toggle sound">🔇</button><input id="rc-vol-slider" type="range" min="0" max="1" step="0.01" value="${currentVol}" />`;
  if (navCta) navCta.insertBefore(ctrl, navCta.firstChild);

  const btn    = document.getElementById('rc-vol-btn');
  const slider = document.getElementById('rc-vol-slider');

  const mobileBtn = null; // mobile mute removed

  function sliderBg(v) {
    if (!slider) return;
    slider.style.background = `linear-gradient(to right, #f97316 0%, #f97316 ${v*100}%, rgba(255,255,255,0.15) ${v*100}%)`;
  }
  if (slider) sliderBg(currentVol);

  function syncIcons() {
    const isOn = music && !muted && music.volume > 0;
    const icon = isOn ? (currentVol < 0.35 ? '🔉' : '🔊') : '🔇';
    if (btn) btn.textContent = icon;
    if (mobileBtn) { mobileBtn.textContent = icon; mobileBtn.classList.toggle('sound-on', isOn); }
  }

  function fadeIn(targetVol) {
    if (!music) {
      music = new Audio('assets/rc-intro.mp3');
      music.loop = true;
      music.volume = 0;
    }
    muted = false;
    const p = music.play();
    if (p) p.catch(() => {});
    let v = music.volume;
    const t = setInterval(() => {
      v = Math.min(v + 0.005, targetVol);
      music.volume = v;
      if (slider) { slider.value = v; sliderBg(v); }
      if (v >= targetVol) { clearInterval(t); syncIcons(); }
    }, 40);
  }

  function toggleMute() {
    if (muted || !music || music.paused || music.volume === 0) {
      muted = false;
      fadeIn(currentVol);
    } else {
      muted = true;
      if (music) music.volume = 0;
      syncIcons();
    }
  }

  if (btn) btn.addEventListener('click', toggleMute);
  if (mobileBtn) mobileBtn.addEventListener('click', toggleMute);

  if (slider) {
    slider.addEventListener('input', () => {
      currentVol = parseFloat(slider.value);
      sessionStorage.setItem(VOL_KEY, currentVol);
      sliderBg(currentVol);
      if (currentVol > 0) {
        muted = false;
        if (!music || music.paused) { fadeIn(currentVol); }
        else { music.volume = currentVol; }
      } else {
        muted = true;
        if (music) music.volume = 0;
      }
      syncIcons();
    });
  }

  // Exposed for intro sequence
  window.rcAudio = {
    enable() { ctrl.classList.add('visible'); },
    startMusic() {
      ctrl.classList.add('visible');
      fadeIn(currentVol);
    }
  };
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
