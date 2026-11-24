// Reality Check Watch + episode pages
(function () {
  // ── Light YouTube players: the real player only loads on click ──
  function embedUrl(id, start) {
    return 'https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0&modestbranding=1' + (start ? '&start=' + start : '');
  }
  function play(box, start) {
    if (!box) return;
    var id = box.dataset.id;
    var iframe = box.querySelector('iframe');
    if (!iframe) {
      iframe = document.createElement('iframe');
      iframe.title = box.dataset.title || 'Reality Check episode';
      iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      iframe.allowFullscreen = true;
      box.innerHTML = '';
      box.appendChild(iframe);
      box.classList.add('is-playing');
    }
    iframe.src = embedUrl(id, start || 0);
  }
  document.addEventListener('click', function (e) {
    var box = e.target.closest('.lite-yt');
    if (box && !box.classList.contains('is-playing')) { play(box, 0); return; }

    // Chapters jump the nearest player
    var ch = e.target.closest('.chapter');
    if (ch) {
      var scope = ch.closest('.featured-grid, .ep-top') || document;
      var player = scope.querySelector('.lite-yt');
      play(player, parseInt(ch.dataset.t, 10) || 0);
      document.querySelectorAll('.chapter.active').forEach(function (c) { c.classList.remove('active'); });
      ch.classList.add('active');
      if (player && player.getBoundingClientRect().top < 60) player.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    // Share: copy link
    var share = e.target.closest('.share-btn');
    if (share) {
      var url = share.dataset.url;
      var done = function () { toast('Link copied'); };
      if (navigator.share && /Mobi|Android|iPhone/i.test(navigator.userAgent)) {
        navigator.share({ title: document.title, url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(done, function () { window.prompt('Copy this link', url); });
      } else {
        window.prompt('Copy this link', url);
      }
    }
  });

  function toast(msg) {
    var t = document.querySelector('.toast');
    if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._h);
    t._h = setTimeout(function () { t.classList.remove('show'); }, 1800);
  }

  // ── Live badge: Monday to Friday, 11:00 AM to 12:30 PM Eastern ──
  var badge = document.getElementById('live-badge');
  if (badge) {
    var DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    var update = function () {
      var parts = {};
      new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' })
        .formatToParts(new Date()).forEach(function (p) { parts[p.type] = p.value; });
      var day = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].indexOf(parts.weekday);
      var mins = parseInt(parts.hour, 10) % 24 * 60 + parseInt(parts.minute, 10);
      var weekday = day >= 1 && day <= 5;
      var text = badge.querySelector('.txt');
      if (weekday && mins >= 660 && mins < 750) {
        badge.className = 'show-badge is-live';
        text.textContent = 'Live now';
        return;
      }
      var add = 0;
      if (!(weekday && mins < 660)) {
        do { add++; } while (((day + add) % 7) === 0 || ((day + add) % 7) === 6);
      }
      var when = add === 0 ? 'Today' : add === 1 ? 'Tomorrow' : DAYS[(day + add) % 7];
      badge.className = 'show-badge is-next';
      text.textContent = 'Next show: ' + when + ' at 11:00 AM ET';
    };
    update();
    setInterval(update, 60000);
  }

  // ── Episode library: search, topic chips, sort, load more ──
  var dataEl = document.getElementById('episodes-data');
  var grid = document.getElementById('library-grid');
  if (dataEl && grid) {
    var eps = [];
    try { eps = JSON.parse(dataEl.textContent); } catch (_) {}
    var PAGE = 12;
    var state = { q: '', topic: '', sort: 'new', shown: PAGE };
    var search = document.getElementById('lib-search');
    var sortSel = document.getElementById('lib-sort');
    var more = document.getElementById('lib-more');
    var count = document.getElementById('lib-count');
    var chips = document.querySelectorAll('#lib-chips .chip');

    var esc = function (s) { return String(s || '').replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); };
    var card = function (e) {
      return '<a class="ep-card" href="/watch/' + e.id + '/"><div class="ep-thumb"><img src="https://i.ytimg.com/vi/' + e.id + '/mqdefault.jpg" alt="' + esc(e.title) + '" loading="lazy" width="320" height="180" />' +
        '<span class="ep-dur">' + esc(e.dur) + '</span><span class="ep-play" aria-hidden="true"></span></div>' +
        '<div class="ep-card-body"><h3 class="ep-card-title">' + esc(e.title) + '</h3><div class="ep-meta">' + esc(e.date) +
        (e.live ? '<span class="ep-live-tag">Live</span>' : '') + '</div></div></a>';
    };
    // Lowercase and drop accents so "pokemon" finds "Pokémon"
    var fold = function (t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); };
    eps.forEach(function (e) { e._hay = fold(e.title + ' ' + e.desc + ' ' + (e.tags || []).join(' ')); });
    var filtered = function () {
      var words = fold(state.q).split(/\s+/).filter(Boolean);
      var list = eps.filter(function (e) {
        if (state.topic && (e.tags || []).indexOf(state.topic) === -1) return false;
        var hay = e._hay;
        return words.every(function (w) { return hay.indexOf(w) !== -1; });
      });
      list.sort(function (a, b) {
        if (state.sort === 'old') return a.published < b.published ? -1 : 1;
        if (state.sort === 'long') return b.secs - a.secs;
        return a.published < b.published ? 1 : -1;
      });
      return list;
    };
    var render = function () {
      var list = filtered();
      grid.innerHTML = list.length
        ? list.slice(0, state.shown).map(card).join('')
        : '<div class="lib-empty">No episodes match that search. Try another word or topic.</div>';
      more.style.display = list.length > state.shown ? '' : 'none';
      if (count) count.textContent = list.length + (list.length === 1 ? ' episode' : ' episodes');
    };
    var reset = function () { state.shown = PAGE; render(); };

    if (search) search.addEventListener('input', function () { state.q = search.value; reset(); });
    if (sortSel) sortSel.addEventListener('change', function () { state.sort = sortSel.value; reset(); });
    chips.forEach(function (c) {
      c.addEventListener('click', function () {
        chips.forEach(function (x) { x.classList.remove('active'); });
        c.classList.add('active');
        state.topic = c.dataset.topic;
        reset();
      });
    });
    if (more) more.addEventListener('click', function () { state.shown += PAGE; render(); });

    // Deep link from episode tag chips: /watch/?topic=Gaming#library
    var topic = new URLSearchParams(location.search).get('topic');
    if (topic) {
      chips.forEach(function (c) { if (c.dataset.topic === topic) c.click(); });
    } else {
      render();
    }
  }

  // ── Newsletter forms (The Checkpoint via Make + Brevo) ──
  document.querySelectorAll('.nl-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = form.querySelector('input[type="email"]');
      var btn = form.querySelector('button');
      btn.textContent = 'Subscribing...';
      btn.disabled = true;
      fetch(form.dataset.hook, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: input.value }) })
        .then(function (res) {
          if (!res.ok) throw new Error('failed');
          btn.textContent = "You're in! Next issue lands 7 AM ET";
          btn.style.background = '#22c55e';
          input.value = '';
        })
        .catch(function () { btn.textContent = 'Try again'; btn.disabled = false; });
    });
  });
})();
