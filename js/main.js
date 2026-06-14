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

// ── RC AUDIO SYSTEM ──
(function() {
  const SOUND_KEY = 'rc_sound_enabled';
  const VOL_KEY   = 'rc_volume';
  const MUSIC_SRC  = location.pathname === '/' || location.pathname.endsWith('index.html') && location.pathname.split('/').length <= 2
    ? 'assets/rc-intro.mp3'
    : '../assets/rc-intro.mp3';

  // Resolve correct path based on page depth
  const depth = location.pathname.replace(/\/$/, '').split('/').length;
  const prefix = depth <= 2 ? '' : '../';
  const musicSrc = prefix + 'assets/rc-intro.mp3';

  let music = null;
  let volEnabled = sessionStorage.getItem(SOUND_KEY) === '1';
  let currentVol = parseFloat(sessionStorage.getItem(VOL_KEY) || '0.7');

  // Inject volume control into nav-cta
  const navCta = document.querySelector('.nav-cta');
  if (navCta) {
    const ctrl = document.createElement('div');
    ctrl.id = 'rc-vol-ctrl';
    ctrl.innerHTML = `<button id="rc-vol-btn" title="Toggle sound">🔊</button><input id="rc-vol-slider" type="range" min="0" max="1" step="0.01" value="${currentVol}" />`;
    navCta.insertBefore(ctrl, navCta.firstChild);

    const btn    = document.getElementById('rc-vol-btn');
    const slider = document.getElementById('rc-vol-slider');

    function updateSliderBg(v) {
      slider.style.background = `linear-gradient(to right, #f97316 0%, #f97316 ${v*100}%, rgba(255,255,255,0.15) ${v*100}%)`;
    }
    updateSliderBg(currentVol);

    function updateIcon() {
      if (!music) { btn.textContent = '🔇'; return; }
      btn.textContent = music.volume === 0 ? '🔇' : music.volume < 0.4 ? '🔉' : '🔊';
    }

    function startMusic() {
      if (music) return;
      music = new Audio(musicSrc);
      music.loop = true;
      music.volume = 0;
      music.play().catch(() => {});
      // fade in
      let v = 0;
      const t = setInterval(() => {
        v = Math.min(v + 0.03, currentVol);
        music.volume = v;
        updateSliderBg(v);
        if (v >= currentVol) clearInterval(t);
      }, 40);
      updateIcon();
    }

    slider.addEventListener('input', () => {
      currentVol = parseFloat(slider.value);
      sessionStorage.setItem(VOL_KEY, currentVol);
      if (music) music.volume = currentVol;
      updateSliderBg(currentVol);
      updateIcon();
    });

    btn.addEventListener('click', () => {
      if (!music) {
        sessionStorage.setItem(SOUND_KEY, '1');
        volEnabled = true;
        startMusic();
        ctrl.classList.add('visible');
      } else if (music.volume > 0) {
        music.volume = 0;
        updateIcon();
      } else {
        music.volume = currentVol;
        updateIcon();
      }
    });

    // Show control if sound was previously enabled
    if (volEnabled) {
      ctrl.classList.add('visible');
      // try autoplay on subsequent pages
      if (!location.pathname.endsWith('/') && !location.pathname.endsWith('index.html')) {
        startMusic();
      } else if (location.pathname !== '/' && !location.pathname.match(/^\/index/)) {
        startMusic();
      }
    }
  }

  // Expose for homepage intro to call when locked
  window.rcAudio = {
    enable() {
      volEnabled = true;
      sessionStorage.setItem(SOUND_KEY, '1');
      const ctrl = document.getElementById('rc-vol-ctrl');
      if (ctrl) ctrl.classList.add('visible');
    },
    startMusic() {
      const ctrl = document.getElementById('rc-vol-ctrl');
      if (ctrl) ctrl.classList.add('visible');
      if (music) return;
      music = new Audio(musicSrc);
      music.loop = true;
      music.volume = 0;
      music.play().catch(() => {});
      let v = 0;
      const t = setInterval(() => {
        v = Math.min(v + 0.02, currentVol);
        music.volume = v;
        const slider = document.getElementById('rc-vol-slider');
        if (slider) { slider.value = v; const s=document.getElementById('rc-vol-ctrl'); if(s) s.querySelector('input').style.background=`linear-gradient(to right, #f97316 0%, #f97316 ${v*100}%, rgba(255,255,255,0.15) ${v*100}%)`; }
        if (v >= currentVol) clearInterval(t);
      }, 60);
    },
    get audioCtx() { return null; }
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
