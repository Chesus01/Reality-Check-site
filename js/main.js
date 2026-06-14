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

  // Resolve asset path based on page depth
  const isRoot = location.pathname === '/' || location.pathname.match(/^\/(index\.html)?$/);
  const musicSrc = isRoot ? 'assets/rc-intro.mp3' : '../assets/rc-intro.mp3';

  let music    = null;
  let muted    = false;
  let volEnabled = sessionStorage.getItem(SOUND_KEY) === '1';
  let currentVol = parseFloat(sessionStorage.getItem(VOL_KEY) || '0.5');

  const navCta = document.querySelector('.nav-cta');
  if (!navCta) return;

  const ctrl = document.createElement('div');
  ctrl.id = 'rc-vol-ctrl';
  ctrl.innerHTML = `<button id="rc-vol-btn" title="Toggle sound">🔇</button><input id="rc-vol-slider" type="range" min="0" max="1" step="0.01" value="${currentVol}" />`;
  navCta.insertBefore(ctrl, navCta.firstChild);

  const btn    = document.getElementById('rc-vol-btn');
  const slider = document.getElementById('rc-vol-slider');

  function updateSliderBg(v) {
    slider.style.background = `linear-gradient(to right, #f97316 0%, #f97316 ${v*100}%, rgba(255,255,255,0.15) ${v*100}%)`;
  }
  updateSliderBg(currentVol);

  function updateIcon() {
    btn.textContent = (!music || muted || music.volume === 0) ? '🔇' : currentVol < 0.4 ? '🔉' : '🔊';
  }

  function ensureMusic() {
    if (!music) {
      music = new Audio(musicSrc);
      music.loop = true;
      music.volume = 0;
    }
  }

  function fadeIn(targetVol) {
    ensureMusic();
    muted = false;
    const p = music.play();
    if (p) p.catch(() => {});
    let v = music.volume;
    const t = setInterval(() => {
      v = Math.min(v + 0.02, targetVol);
      music.volume = v;
      slider.value = v;
      updateSliderBg(v);
      if (v >= targetVol) {
        clearInterval(t);
        btn.textContent = targetVol < 0.4 ? '🔉' : '🔊';
        if (document.getElementById('rc-mobile-mute')) document.getElementById('rc-mobile-mute').textContent = targetVol < 0.4 ? '🔉' : '🔊';
      }
    }, 40);
  }

  // Slider — also starts music if it hasn't started yet
  slider.addEventListener('input', () => {
    currentVol = parseFloat(slider.value);
    sessionStorage.setItem(VOL_KEY, currentVol);
    updateSliderBg(currentVol);
    if (currentVol > 0) {
      muted = false;
      if (!music || music.paused) {
        fadeIn(currentVol);
      } else {
        music.volume = currentVol;
      }
    } else {
      muted = true;
      if (music) music.volume = 0;
    }
    updateIcon();
  });

  // Button — toggle mute or first-enable
  btn.addEventListener('click', () => {
    if (!volEnabled) {
      volEnabled = true;
      sessionStorage.setItem(SOUND_KEY, '1');
      ctrl.classList.add('visible');
      fadeIn(currentVol);
    } else if (muted || !music || music.paused || music.volume === 0) {
      muted = false;
      fadeIn(currentVol);
    } else {
      muted = true;
      music.volume = 0;
      updateIcon();
    }
  });

  // Mobile floating mute button
  const mobileBtn = document.createElement('button');
  mobileBtn.id = 'rc-mobile-mute';
  mobileBtn.title = 'Toggle sound';
  mobileBtn.textContent = '🔇';
  document.body.appendChild(mobileBtn);

  function syncMobileBtn() {
    mobileBtn.textContent = (!music || muted || music.volume === 0) ? '🔇' : '🔊';
    mobileBtn.classList.toggle('sound-on', !(!music || muted || music.volume === 0));
  }

  mobileBtn.addEventListener('click', () => {
    if (!volEnabled) {
      volEnabled = true;
      sessionStorage.setItem(SOUND_KEY, '1');
      ctrl.classList.add('visible');
      fadeIn(currentVol);
    } else if (muted || !music || music.paused || music.volume === 0) {
      muted = false;
      fadeIn(currentVol);
    } else {
      muted = true;
      music.volume = 0;
      updateIcon();
    }
    syncMobileBtn();
  });

  // Keep mobile btn in sync when desktop controls change
  const origUpdateIcon = updateIcon;
  function updateIcon() {
    origUpdateIcon();
    syncMobileBtn();
  }

  // Auto-resume on non-homepage pages if previously enabled
  if (volEnabled) {
    ctrl.classList.add('visible');
    if (!isRoot) fadeIn(currentVol);
  }

  // Exposed for homepage intro sequence
  window.rcAudio = {
    enable() {
      volEnabled = true;
      sessionStorage.setItem(SOUND_KEY, '1');
      ctrl.classList.add('visible');
    },
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
