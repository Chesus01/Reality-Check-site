#!/usr/bin/env python3
"""Reality Check video feed and Watch section builder.

1. Fetch (only when YOUTUBE_API_KEY is set): reads the channel uploads playlist
   (playlistItems, 1 quota unit a call) and video details (videos, 1 unit per
   50 ids). Writes data/episodes.json, data/shorts.json, data/interviews.json,
   data/latest-videos.json and keeps every episode ever seen in
   data/episode-archive.json so episode pages never disappear.
2. Render (always): writes /watch/<id>/index.html for every archived episode,
   fills the BUILD markers in watch/index.html and index.html, and writes
   sitemap.xml and robots.txt.

If the API call fails, the last good data is kept and the pages still render.
"""
import datetime as dt
import html
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
SITE = "https://rcweb3.xyz"
CHANNEL_ID = "UCoXM9ehSmDW-VaRltwiWXwQ"
UPLOADS_PLAYLIST = "UU" + CHANNEL_ID[2:]
INTERVIEWS_PLAYLIST_ID = os.environ.get("INTERVIEWS_PLAYLIST_ID", "").strip()
MAX_EPISODES = 60
MAX_SHORTS = 12
SHORT_MAX_SECONDS = 180
NEWSLETTER_HOOK = "https://hook.us2.make.com/jh06mlsk6gid56s52oypwek3sb4cotaj"

# Used until an interviews playlist id is set (the Abstract one is removed).
FALLBACK_INTERVIEWS = [
    {"id": "UpkfbNVKi1Y", "title": "Reality Check with Diam: L1 Quantum Safe Blockchain"},
    {"id": "umWTtU-U4Z8", "title": "Reality Check: Chimpers / Online Shop & Dojo"},
]

TOPICS = [
    ("Crypto & Markets", r"(\$[a-z]{2,12}\b|\b(crypto|hacks?|exploits?|binance|coinbase|kraken|ledger|bitget|pump ?fun|defi|robinhood chain|onchain|chain|stablecoins?|airdrops?|cpi|inflation|rates?|jobs report|recession|bitcoin|btc|eth|ethereum|solana|sol|xrp|altcoins?|memecoins?|tokens?|markets?|trading|perps|etfs?|fed|macro|stocks?|nasdaq|bull|bear(ish)? market|bottom|pump|dump|price|\d+k)\b)"),
    ("NFTs & Culture", r"\b(nfts?|pfps?|mint(ing|s)?|opensea|blur|ordinals|creepz|chimpers|pudgy|penguins|culture|memes?|art|collectors?|genuine undead)\b"),
    ("Pokémon & TCG", r"(pok[eé]mon|\btcg\b|card ?wall|one piece|\bslabs?\b|\bpsa\b|\bcards?\b|\bpulls?\b|booster|graded)"),
    ("Gaming", r"\b(gaming|games?|gamers?|esports|blinko|arcade|steam|play to earn|playtest|gta ?6?|nintendo|switch 2|playstation|ps5|xbox|fortnite|roblox|casino|ryft)\b"),
    ("Interviews", r"(\binterviews?\b|\bfounders?\b|\bama\b|\bceo\b|\bcto\b|\bsits? down\b|\b1 ?on ?1\b|\bone on one\b|^reality check with\b|\bjoins reality check\b|\bof \w+ joins\b)"),
    ("AI & Tech", r"\b(ai|a\.i\.|anthropic|openai|chatgpt|claude|grok|gemini|nvidia|tech|quantum|robots?|apple|google|tesla|agents?)\b"),
]

# Opening words of the standard paragraphs every episode description repeats.
BOILERPLATE = (
    "plus our daily cardwall segment", "today's partners", "todays partners", "reality check is a live",
    "live monday through friday", "every show includes", "we question everything", "follow along for",
    "follow on x", "question. think. verify", "#", "http", "shop graded cards",
)

CHAPTER_RE = re.compile(r"^\s*[\(\[]?((?:\d{1,2}:)?\d{1,2}:\d{2})[\)\]]?\s*[-–—:|•>]*\s*(.+?)\s*$")


# ───────────────────────── helpers ─────────────────────────
def esc(s):
    return html.escape(s or "", quote=True)


def parse_iso_duration(iso):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def dur_text(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m" if m else f"{h}h"
    if m:
        return f"{m}m"
    return f"{s}s"


def iso_duration(sec):
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    out = "PT"
    if h:
        out += f"{h}H"
    if m:
        out += f"{m}M"
    if s or out == "PT":
        out += f"{s}S"
    return out


def ts_to_sec(ts):
    parts = [int(p) for p in ts.split(":")]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def parse_chapters(desc):
    chapters = []
    for line in (desc or "").splitlines():
        m = CHAPTER_RE.match(line)
        if m and m.group(2):
            chapters.append({"t": ts_to_sec(m.group(1)), "time": m.group(1), "label": m.group(2)[:120]})
    # Only real chapter lists count: at least 2 and in time order.
    if len(chapters) < 2 or any(b["t"] <= a["t"] for a, b in zip(chapters, chapters[1:])):
        return []
    return chapters


def summary(desc, limit=220):
    """Short readable summary: drops chapter lines, links and hashtag lines."""
    keep = []
    for line in (desc or "").splitlines():
        if CHAPTER_RE.match(line) or re.match(r"^\s*#", line):
            continue
        line = re.sub(r"https?://\S+", "", line).strip()
        if line:
            keep.append(line)
    text = re.sub(r"\s+", " ", " ".join(keep)).strip()
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."
    return text


def topic_tags(title, desc, is_interview=False):
    # Topics read the title plus the start of the description (boilerplate links
    # and sponsor reads usually sit lower down). Interviews come from the title
    # or the interviews playlist only, so "with Kenny" in a description doesn't count.
    title_l = (title or "").lower()
    # The episode's own summary is the first paragraph. Later paragraphs are the
    # standard show text that every episode repeats, so they would tag everything.
    first_para = ""
    for para in re.split(r"\n\s*\n", (desc or "").strip()):
        lines = [l for l in para.splitlines() if not l.strip().lower().startswith(BOILERPLATE)]
        if lines:
            first_para = "\n".join(lines)
            break
    text = f"{title_l}\n{first_para[:400].lower()}"
    tags = []
    for name, rx in TOPICS:
        hay = title_l if name == "Interviews" else text
        if re.search(rx, hay, re.I):
            tags.append(name)
    if is_interview and "Interviews" not in tags:
        tags.append("Interviews")
    return tags


def nice_date(iso):
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d.strftime("%b %-d, %Y")
    except Exception:
        return ""


def best_thumb(thumbs, vid):
    for k in ("maxres", "standard", "high", "medium", "default"):
        if thumbs.get(k, {}).get("url"):
            return thumbs[k]["url"].split("?")[0]
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def card_thumb(vid):
    return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path, obj):
    """Write JSON, but skip the write when only the "updated" stamp would change."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and isinstance(obj, dict):
        old = read_json(path, None)
        if isinstance(old, dict) and {k: v for k, v in old.items() if k != "updated"} == {k: v for k, v in obj.items() if k != "updated"}:
            return False
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return True


def write_if_changed(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


# ───────────────────────── fetch ─────────────────────────
def api(endpoint, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    url = f"https://www.googleapis.com/youtube/v3/{endpoint}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def playlist_ids(playlist_id, max_pages):
    ids, token = [], None
    for _ in range(max_pages):
        p = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50}
        if token:
            p["pageToken"] = token
        data = api("playlistItems", **p)
        ids += [it["contentDetails"]["videoId"] for it in data.get("items", [])]
        token = data.get("nextPageToken")
        if not token:
            break
    return ids


def video_details(ids):
    items = []
    for i in range(0, len(ids), 50):
        data = api("videos", part="snippet,contentDetails,liveStreamingDetails", id=",".join(ids[i:i + 50]), maxResults=50)
        items += data.get("items", [])
    order = {v: n for n, v in enumerate(ids)}
    return sorted(items, key=lambda it: order.get(it["id"], 10 ** 9))


def to_record(item, interview_ids=()):
    sn, cd = item["snippet"], item["contentDetails"]
    live = item.get("liveStreamingDetails") or {}
    secs = parse_iso_duration(cd.get("duration"))
    desc = sn.get("description", "")
    published = live.get("actualStartTime") or sn.get("publishedAt", "")
    vid = item["id"]
    return {
        "id": vid,
        "title": sn.get("title", "").strip(),
        "published": published,
        "duration_seconds": secs,
        "duration": dur_text(secs),
        "description": desc[:400],
        "description_full": desc,
        "thumbnail": best_thumb(sn.get("thumbnails", {}), vid),
        "live_stream": bool(live.get("actualStartTime")),
        "chapters": parse_chapters(desc),
        "tags": topic_tags(sn.get("title", ""), desc, vid in interview_ids),
        "broadcast": sn.get("liveBroadcastContent", "none"),
    }


def public(rec):
    out = {k: v for k, v in rec.items() if k not in ("description_full", "broadcast")}
    return out


def fetch():
    interview_items = []
    if INTERVIEWS_PLAYLIST_ID:
        iids = playlist_ids(INTERVIEWS_PLAYLIST_ID, 2)
        interview_items = video_details(iids)
    interview_ids = {it["id"] for it in interview_items} or {v["id"] for v in FALLBACK_INTERVIEWS}

    ids = playlist_ids(UPLOADS_PLAYLIST, 6)
    episodes, shorts = [], []
    for item in video_details(ids):
        rec = to_record(item, interview_ids)
        if rec["broadcast"] != "none" or rec["duration_seconds"] == 0:
            continue  # live right now or scheduled; picked up once it is a VOD
        if rec["duration_seconds"] > SHORT_MAX_SECONDS:
            if len(episodes) < MAX_EPISODES:
                episodes.append(rec)
        elif len(shorts) < MAX_SHORTS:
            shorts.append(rec)
    if not episodes:
        raise RuntimeError("YouTube returned no episodes")
    episodes.sort(key=lambda r: r["published"], reverse=True)

    if interview_items:
        interviews = [public(to_record(it, interview_ids)) for it in interview_items
                      if it["snippet"].get("liveBroadcastContent", "none") == "none"]
        interviews.sort(key=lambda r: r["published"], reverse=True)
    else:
        interviews = [dict(v, thumbnail=f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg") for v in FALLBACK_INTERVIEWS]

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"
    archive = read_json(DATA / "episode-archive.json", {"episodes": {}})
    for rec in episodes:
        archive["episodes"][rec["id"]] = {k: v for k, v in rec.items() if k != "broadcast"}
    archive["updated"] = now

    write_json(DATA / "episodes.json", {"updated": now, "episodes": [public(r) for r in episodes]})
    write_json(DATA / "shorts.json", {"updated": now, "shorts": [public(r) for r in shorts]})
    write_json(DATA / "interviews.json", {"updated": now, "playlist_id": INTERVIEWS_PLAYLIST_ID or None, "interviews": interviews})
    write_json(DATA / "episode-archive.json", archive)
    write_json(DATA / "latest-videos.json", {
        "videos": [{"id": r["id"], "title": r["title"], "thumbnail": r["thumbnail"]} for r in episodes[:6]],
        "updated": now,
    })
    print(f"Fetched {len(episodes)} episodes, {len(shorts)} shorts, {len(interviews)} interviews")


# ───────────────────────── shared markup ─────────────────────────
ICONS = {
    "tiktok": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M19.6 6.7a4.8 4.8 0 0 1-3.8-4.2V2h-3.4v13.4a2.9 2.9 0 1 1-2-2.7V9.2a6.3 6.3 0 1 0 5.4 6.2V8.6a8.2 8.2 0 0 0 4.8 1.5V6.7h-1z"/></svg>',
    "instagram": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1.2" fill="currentColor" stroke="none"/></svg>',
    "youtube": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2 31 31 0 0 0 0 12a31 31 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31 31 0 0 0 24 12a31 31 0 0 0-.5-5.8zM9.6 15.6V8.4l6.2 3.6-6.2 3.6z"/></svg>',
    "x": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.748l7.73-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>',
    "kick": '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M3 3h5v4h2V5h2V3h9v6h-2v2h-2v2h2v2h2v6h-9v-2h-2v-2H8v4H3V3z"/></svg>',
}
SOCIALS = [
    ("tiktok", "TikTok", "https://www.tiktok.com/@chesus_02"),
    ("instagram", "Instagram", "https://www.instagram.com/chesus02/"),
    ("youtube", "YouTube", "https://www.youtube.com/@RealityCheckWeb3"),
    ("x", "X", "https://x.com/chesus"),
    ("kick", "Kick", "https://kick.com/chesus"),
]


def social_icons(cls="social-icons"):
    links = "".join(
        f'<a href="{url}" target="_blank" rel="noopener" aria-label="Chesus on {label}" title="{label}">{ICONS[key]}</a>'
        for key, label, url in SOCIALS
    )
    return f'<div class="{cls}">{links}</div>'


NAV = """<nav>
  <a href="/" class="nav-logo">
    <img src="/assets/RC Favicon Logo.png" alt="Reality Check" />
    <span class="nav-logo-text">Reality Check</span>
  </a>
  <ul class="nav-links">
    <li><a href="/">Home</a></li>
    <li><a href="/watch">Watch</a></li>
    <li><a href="/sponsors">Sponsors</a></li>
    <li><a href="/partners">Partner With Us</a></li>
    <li><a href="/newsletter">Newsletter</a></li>
    <li class="nav-dropdown">
      <a href="#">The Team &#9660;</a>
      <div class="nav-dropdown-menu">
        <a href="/chesus">Chesus</a>
        <a href="/kennypowerz">Kenny Powerz</a>
        <a href="/anidiot">AnIdiot</a>
      </div>
    </li>
  </ul>
  <div class="nav-cta">
    <a href="https://x.com/RealityCheck_RR" target="_blank" rel="noopener">
      <svg class="x-icon" viewBox="0 0 24 24"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.748l7.73-8.835L1.254 2.25H8.08l4.253 5.622L18.244 2.25zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
      Follow on X
    </a>
  </div>
  <div class="hamburger" aria-label="Toggle navigation" role="button" tabindex="0">
    <span></span><span></span><span></span>
  </div>
</nav>
<div class="mobile-nav">
  <a href="/">Home</a>
  <a href="/watch">Watch</a>
  <a href="/sponsors">Sponsors</a>
  <a href="/partners">Partner With Us</a>
  <a href="/newsletter">Newsletter</a>
  <span class="mobile-nav-label">The Team</span>
  <a href="/chesus" class="mobile-nav-sub">Chesus</a>
  <a href="/kennypowerz" class="mobile-nav-sub">Kenny Powerz</a>
  <a href="/anidiot" class="mobile-nav-sub">AnIdiot</a>
  <a href="https://discord.gg/xngreYDBMC" target="_blank" rel="noopener" style="color:#a5aeff;font-weight:700;">Join Discord</a>
</div>"""


def footer():
    return f"""<footer>
  <a href="/" class="footer-logo">
    <img src="/assets/RC Favicon Logo.png" alt="Reality Check" />
    <span style="font-weight:700;font-size:14px;color:var(--text);">Reality Check</span>
  </a>
  <span class="footer-copy">Live Monday to Friday &middot; 11 AM ET</span>
  <div class="footer-links">
    <a href="/watch">Watch</a>
    <a href="/partners">Partner With Us</a>
    <a href="/chesus">Chesus</a>
    <a href="/kennypowerz">Kenny Powerz</a>
    <a href="/anidiot">AnIdiot</a>
    <a href="mailto:realitycheckrr@gmail.com">Contact</a>
  </div>
  <!-- FOOTER-SOCIALS -->{social_icons("footer-socials")}<!-- /FOOTER-SOCIALS -->
</footer>"""


NEWSLETTER = f"""<section class="section nl-band" id="newsletter">
    <div class="section-inner nl-inner">
      <div>
        <p class="section-label">The Checkpoint</p>
        <h2>Get the daily <span class="orange">Web3 briefing.</span></h2>
        <p class="nl-sub">Crypto, NFTs, markets, gaming and the signal that matters, in your inbox every weekday at 7 AM ET. Free.</p>
      </div>
      <form class="nl-form" data-hook="{NEWSLETTER_HOOK}">
        <input type="email" required placeholder="Enter your email address" aria-label="Email address" />
        <button type="submit" class="btn btn-orange">Subscribe Free</button>
      </form>
    </div>
  </section>"""


def ep_card(ep, heading="h3"):
    vid = ep["id"]
    live = '<span class="ep-live-tag">Live</span>' if ep.get("live_stream") else ""
    return (
        f'<a class="ep-card" href="/watch/{vid}/">'
        f'<div class="ep-thumb"><img src="{card_thumb(vid)}" alt="{esc(ep["title"])}" loading="lazy" width="320" height="180" />'
        f'<span class="ep-dur">{esc(ep.get("duration", ""))}</span><span class="ep-play" aria-hidden="true"></span></div>'
        f'<div class="ep-card-body"><{heading} class="ep-card-title">{esc(ep["title"])}</{heading}>'
        f'<div class="ep-meta">{nice_date(ep.get("published", ""))}{live}</div></div></a>'
    )


def lite_player(ep, cls="lite-yt"):
    vid = ep["id"]
    return (
        f'<div class="{cls}" data-id="{vid}" data-title="{esc(ep["title"])}">'
        f'<img src="{esc(ep["thumbnail"])}" alt="{esc(ep["title"])}" loading="eager" />'
        f'<button class="lite-play" type="button" aria-label="Play {esc(ep["title"])}"></button></div>'
    )


def chapters_list(ep):
    if not ep.get("chapters"):
        return ""
    items = "".join(
        f'<li><button type="button" class="chapter" data-t="{c["t"]}"><span class="ch-time">{esc(c["time"])}</span><span class="ch-label">{esc(c["label"])}</span></button></li>'
        for c in ep["chapters"]
    )
    return f'<ol class="chapters">{items}</ol>'


def tag_chips(ep):
    return "".join(f'<a class="tag-chip" href="/watch/?topic={urllib.parse.quote(t)}#library">{esc(t)}</a>' for t in ep.get("tags", []))


def linkify(text):
    out = esc(text)
    out = re.sub(r"(https?://[^\s<]+)", lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener nofollow">{m.group(1)}</a>', out)
    return out.replace("\n", "<br>")


def share_buttons(ep):
    vid = ep["id"]
    return (
        f'<div class="ep-actions"><button type="button" class="btn btn-outline share-btn" data-url="{SITE}/watch/{vid}/">Share</button>'
        f'<a class="btn btn-orange" href="https://www.youtube.com/watch?v={vid}" target="_blank" rel="noopener">Watch on YouTube &#8599;</a></div>'
    )


# ───────────────────────── episode pages ─────────────────────────
def episode_page(ep, all_eps):
    vid = ep["id"]
    url = f"{SITE}/watch/{vid}/"
    desc_full = ep.get("description_full") or ep.get("description", "")
    short_desc = summary(desc_full, 200) or f"Reality Check episode: {ep['title']}"
    related = [o for o in all_eps if o["id"] != vid and set(o.get("tags", [])) & set(ep.get("tags", []))][:3]
    if len(related) < 3:
        related += [o for o in all_eps if o["id"] != vid and o not in related][: 3 - len(related)]
    ld = {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "name": ep["title"],
        "description": short_desc,
        "thumbnailUrl": [ep["thumbnail"]],
        "uploadDate": ep.get("published"),
        "duration": iso_duration(ep.get("duration_seconds", 0)),
        "embedUrl": f"https://www.youtube.com/embed/{vid}",
        "contentUrl": f"https://www.youtube.com/watch?v={vid}",
        "url": url,
        "publisher": {"@type": "Organization", "name": "Reality Check", "url": SITE + "/",
                      "logo": {"@type": "ImageObject", "url": SITE + "/assets/RC%20Favicon%20Logo.png"}},
    }
    if ep.get("live_stream"):
        ld["publication"] = {"@type": "BroadcastEvent", "isLiveBroadcast": True, "startDate": ep.get("published")}
    meta_line = f'{nice_date(ep.get("published", ""))} &middot; {esc(ep.get("duration", ""))}'
    if ep.get("live_stream"):
        meta_line += ' &middot; <span class="ep-live-tag">Live stream</span>'
    chapters = chapters_list(ep)
    chapters_block = f'<aside class="ep-chapters"><h2>Chapters</h2>{chapters}</aside>' if chapters else ""
    title_t = esc(ep["title"])
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title_t} | Reality Check</title>
  <meta name="description" content="{esc(short_desc)}" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="video.other" />
  <meta property="og:site_name" content="Reality Check" />
  <meta property="og:url" content="{url}" />
  <meta property="og:title" content="{title_t}" />
  <meta property="og:description" content="{esc(short_desc)}" />
  <meta property="og:image" content="{esc(ep['thumbnail'])}" />
  <meta property="og:video" content="https://www.youtube.com/embed/{vid}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:site" content="@RealityCheck_RR" />
  <meta name="twitter:title" content="{title_t}" />
  <meta name="twitter:description" content="{esc(short_desc)}" />
  <meta name="twitter:image" content="{esc(ep['thumbnail'])}" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet" />
  <link rel="stylesheet" href="/css/style.css" />
  <link rel="stylesheet" href="/css/watch.css" />
  <link rel="icon" href="/assets/RC Favicon Logo.png" type="image/png" />
  <link rel="apple-touch-icon" href="/assets/RC Favicon Logo.png" />
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body class="ep-page">
{NAV}
<main>
  <section class="section ep-top">
    <div class="section-inner">
      <a class="ep-back" href="/watch/">&#8592; All episodes</a>
      {lite_player(ep, "lite-yt ep-player")}
      <div class="ep-head">
        <div class="tag-row">{tag_chips(ep)}</div>
        <h1 class="ep-title">{title_t}</h1>
        <div class="ep-meta-line">{meta_line}</div>
        {share_buttons(ep)}
      </div>
      <div class="ep-cols{' has-chapters' if chapters else ''}">
        <div class="ep-desc"><h2>About this episode</h2><div class="ep-desc-text">{linkify(desc_full) or 'Reality Check, the daily Web3 show.'}</div></div>
        {chapters_block}
      </div>
    </div>
  </section>
  <section class="section ep-related">
    <div class="section-inner">
      <p class="section-label">Keep watching</p>
      <h2>More episodes <span class="orange">like this.</span></h2>
      <div class="ep-grid">{''.join(ep_card(o) for o in related)}</div>
      <div class="center-row"><a class="btn btn-outline" href="/watch/#library">See all episodes</a></div>
    </div>
  </section>
  {NEWSLETTER}
</main>
{footer()}
<script src="/js/main.js"></script>
<script src="/js/watch.js"></script>
</body>
</html>
"""


# ───────────────────────── marker filling ─────────────────────────
def fill(text, name, content):
    pat = re.compile(rf"(<!-- BUILD:{name} -->)(.*?)(<!-- /BUILD:{name} -->)", re.S)
    if not pat.search(text):
        raise RuntimeError(f"marker BUILD:{name} missing")
    return pat.sub(lambda m: m.group(1) + content + m.group(3), text)


def short_card(s):
    return (
        f'<a class="short-card" href="https://www.youtube.com/shorts/{s["id"]}" target="_blank" rel="noopener">'
        f'<img src="https://i.ytimg.com/vi/{s["id"]}/hqdefault.jpg" alt="{esc(s["title"])}" loading="lazy" />'
        f'<span class="short-title">{esc(s["title"])}</span></a>'
    )


def interview_card(iv, archive_ids):
    vid = iv["id"]
    if vid in archive_ids:
        href, extra = f"/watch/{vid}/", ""
    else:
        href, extra = f"https://www.youtube.com/watch?v={vid}", ' target="_blank" rel="noopener"'
    return (
        f'<a class="ep-card" href="{href}"{extra}><div class="ep-thumb"><img src="{card_thumb(vid)}" alt="{esc(iv["title"])}" loading="lazy" width="320" height="180" />'
        f'<span class="ep-play" aria-hidden="true"></span></div><div class="ep-card-body"><h3 class="ep-card-title">{esc(iv["title"])}</h3>'
        f'<div class="ep-meta">Founder Series</div></div></a>'
    )


def render_watch(episodes, shorts, interviews, archive_ids):
    path = ROOT / "watch" / "index.html"
    text = path.read_text(encoding="utf-8")
    if "<!-- BUILD:featured -->" not in text:
        print("watch/index.html has no BUILD markers yet; skipping")
        return False
    latest = episodes[0]
    latest_desc = esc(summary(latest.get("description", "")))
    featured = (
        f'<div class="featured-grid"><div>{lite_player(latest, "lite-yt featured-player")}</div>'
        f'<div class="featured-info"><div class="featured-label">&#9654; Latest episode</div>'
        f'<h2 class="featured-title"><a href="/watch/{latest["id"]}/">{esc(latest["title"])}</a></h2>'
        f'<div class="ep-meta-line">{nice_date(latest.get("published", ""))} &middot; {esc(latest.get("duration", ""))}</div>'
        f'<p class="featured-desc">{latest_desc}</p>'
        f'{chapters_list(latest)}{share_buttons(latest)}</div></div>'
    )
    data = [{
        "id": e["id"], "title": e["title"], "published": e.get("published", ""), "date": nice_date(e.get("published", "")),
        "secs": e.get("duration_seconds", 0), "dur": e.get("duration", ""), "desc": e.get("description", ""),
        "tags": e.get("tags", []), "live": e.get("live_stream", False),
    } for e in episodes]
    counts = {name: sum(1 for e in episodes if name in e.get("tags", [])) for name, _ in TOPICS}
    chips = '<button type="button" class="chip active" data-topic="">All</button>' + "".join(
        f'<button type="button" class="chip" data-topic="{esc(name)}">{esc(name)}</button>' for name, _ in TOPICS if counts[name]
    )
    text = fill(text, "featured", featured)
    text = fill(text, "chips", chips)
    text = fill(text, "library", "".join(ep_card(e) for e in episodes[:12]))
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    text = fill(text, "library-data", '<script type="application/json" id="episodes-data">' + data_json + "</script>")
    text = fill(text, "interviews", "".join(interview_card(i, archive_ids) for i in interviews[:9]))
    text = fill(text, "shorts", "".join(short_card(s) for s in shorts) or '<p class="muted-note">New Shorts land here soon.</p>')
    text = fill(text, "count", str(len(episodes)))
    return write_if_changed(path, text)


def render_home(episodes):
    path = ROOT / "index.html"
    text = path.read_text(encoding="utf-8")
    if len(episodes) < 3 or "<!-- BUILD:home-latest -->" not in text:
        return False  # keep the last good list already in the page
    text = fill(text, "home-latest", "".join(ep_card(e) for e in episodes[:3]))
    return write_if_changed(path, text)


STATIC_PAGES = ["", "watch/", "sponsors/", "partners/", "newsletter/", "chesus/", "kennypowerz/", "anidiot/"]


def render_sitemap(archive):
    today = dt.date.today().isoformat()
    rows = [f"  <url><loc>{SITE}/{p}</loc><lastmod>{today}</lastmod></url>" for p in STATIC_PAGES]
    eps = sorted(archive.values(), key=lambda e: e.get("published", ""), reverse=True)
    for e in eps:
        lastmod = (e.get("published") or today)[:10]
        vdesc = esc(summary(e.get("description", ""), 2000) or e["title"])
        rows.append(
            f"  <url><loc>{SITE}/watch/{e['id']}/</loc><lastmod>{lastmod}</lastmod>"
            f"<video:video><video:thumbnail_loc>{esc(e['thumbnail'])}</video:thumbnail_loc>"
            f"<video:title>{esc(e['title'])}</video:title>"
            f"<video:description>{vdesc}</video:description>"
            f"<video:player_loc>https://www.youtube.com/embed/{e['id']}</video:player_loc>"
            f"<video:duration>{int(e.get('duration_seconds', 0))}</video:duration></video:video></url>"
        )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">\n'
           + "\n".join(rows) + "\n</urlset>\n")
    # lastmod for static pages changes daily; only write when episodes changed or file missing
    path = ROOT / "sitemap.xml"
    write_if_changed(ROOT / "robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    static_lastmod = re.compile(r"(<loc>[^<]*</loc>)<lastmod>[^<]*</lastmod>(</url>)")
    if old and static_lastmod.sub(r"\1\2", old) == static_lastmod.sub(r"\1\2", xml):
        return False  # only the daily date on static pages changed; skip the commit noise
    path.write_text(xml, encoding="utf-8")
    return True


def render():
    archive = read_json(DATA / "episode-archive.json", {"episodes": {}})["episodes"]
    episodes = read_json(DATA / "episodes.json", {"episodes": []})["episodes"]
    shorts = read_json(DATA / "shorts.json", {"shorts": []})["shorts"]
    interviews = read_json(DATA / "interviews.json", {"interviews": []})["interviews"]
    if not episodes:
        print("No episode data yet; nothing to render")
        return
    all_eps = sorted(archive.values(), key=lambda e: e.get("published", ""), reverse=True)
    pages = 0
    for ep in all_eps:
        if write_if_changed(ROOT / "watch" / ep["id"] / "index.html", episode_page(ep, all_eps)):
            pages += 1
    render_watch(episodes, shorts, interviews, set(archive))
    render_home(episodes)
    render_sitemap(archive)
    print(f"Rendered {len(all_eps)} episode pages ({pages} changed), watch page, home page, sitemap")


def main():
    if os.environ.get("YOUTUBE_API_KEY") and "--no-fetch" not in sys.argv:
        try:
            fetch()
        except Exception as exc:  # keep last good data, still render
            print(f"::warning::YouTube fetch failed, keeping last good data: {exc}")
    render()


if __name__ == "__main__":
    main()
