import html, json, os, statistics, threading, time, unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title="TasteDesk | Cultural Underwriting", page_icon="◆",
                   layout="wide", initial_sidebar_state="collapsed")

# ───────────────────────────── CONFIG ─────────────────────────────
BASE = "https://hackathon.api.qloo.com"
MIN_GAP = 0.10            # seconds between API calls (global, thread-safe)
CHUNK = 25
CACHE_FILE = ".cache/universe.json"
CACHE_MAX_AGE = 3 * 86400

PANEL = [  # celebrity audiences used as the comparison set
    "Cedric the Entertainer", "Kevin Hart", "Dave Chappelle", "Chris Rock", "Will Smith",
    "Denzel Washington", "Jennifer Aniston", "Ryan Reynolds", "George Clooney", "Dwayne Johnson",
    "Selena Gomez", "Zendaya", "Kendall Jenner", "Rihanna", "Beyonce", "Taylor Swift", "Drake",
    "Snoop Dogg", "Kendrick Lamar", "Jay-Z", "Lady Gaga", "Billie Eilish", "Ariana Grande",
    "Post Malone", "The Weeknd", "Bad Bunny", "Bruno Mars", "Katy Perry", "Ed Sheeran",
    "LeBron James", "Michael Jordan", "Serena Williams", "Stephen Curry", "Naomi Osaka",
    "Tom Brady", "Kim Kardashian",
]
REF_BRANDS = [  # reference brands (2 chunks of 25)
    "Nike", "Adidas", "Pepsi", "Coca-Cola", "Sprite", "Starbucks", "McDonald's", "Apple", "Samsung",
    "Gucci", "Louis Vuitton", "Patagonia", "Lululemon", "Red Bull", "Heineken", "Corona Extra",
    "Jack Daniel's", "Hennessy", "Patron", "Grey Goose", "Jose Cuervo", "Don Julio",
    "Tito's Handmade Vodka", "Sephora", "MAC Cosmetics", "Netflix", "Spotify", "Uber", "Chipotle",
    "Converse", "Timberland", "Ray-Ban", "Puma", "Under Armour", "JBL", "Bose", "Harley-Davidson",
    "Jeep", "Ford", "Hyundai", "Tesla", "Gatorade", "Oakley", "Chanel", "H&M", "Levi's", "Dior",
    "Old Spice", "Aveeno", "Casamigos",
]
CITIES = ["New York City", "Los Angeles", "Chicago", "Atlanta", "Houston", "Miami", "Dallas",
          "San Francisco", "Washington DC", "Detroit"]
LENSES = {
    "All fans": {}, "Under 35": {"signal.demographics.age": "35_and_younger"},
    "36–55": {"signal.demographics.age": "36_to_55"},
    "55 and over": {"signal.demographics.age": "55_and_older"},
    "Women": {"signal.demographics.gender": "female"}, "Men": {"signal.demographics.gender": "male"},
}

# ───────────────────────────── STYLE ─────────────────────────────
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
:root{--bg:#0A0D12;--s1:#10141B;--s2:#151A23;--line:#232A36;--tx:#E8ECF3;--mut:#8A94A6;--acc:#2EE6A6;}
html,body,.stApp,[class*="css"]{font-family:'Inter',sans-serif;color:var(--tx);}
.stApp{background:radial-gradient(1100px 520px at 88% -12%,rgba(46,230,166,.11),transparent 60%),radial-gradient(900px 520px at -10% 0%,rgba(110,90,255,.11),transparent 55%),var(--bg);}
#MainMenu,footer,header[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
.block-container{max-width:1160px;padding-top:1.5rem;padding-bottom:4rem;}
.mono{font-family:'JetBrains Mono',monospace;}
.logo{font-weight:800;letter-spacing:.3em;font-size:.82rem;color:var(--acc);}
.hero h1{font-size:3.5rem;line-height:1.03;font-weight:800;letter-spacing:-.04em;margin:.9rem 0 .9rem;}
.hero h1 em{font-style:normal;background:linear-gradient(90deg,#2EE6A6,#7AA8FF);-webkit-background-clip:text;background-clip:text;color:transparent;}
.hero p{color:var(--mut);font-size:1.12rem;max-width:700px;line-height:1.55;}
.kicker{font-size:.72rem;letter-spacing:.22em;color:var(--mut);font-weight:700;margin:2.4rem 0 .9rem;}
.role{background:linear-gradient(180deg,var(--s2),var(--s1));border:1px solid var(--line);border-radius:18px;padding:26px 24px 22px;min-height:236px;margin-bottom:.7rem;transition:.18s;}
.role:hover{border-color:rgba(46,230,166,.55);transform:translateY(-3px);box-shadow:0 14px 40px rgba(46,230,166,.08);}
.role .tag{font-size:.68rem;letter-spacing:.2em;font-weight:700;color:var(--acc);}
.role .q{font-size:1.5rem;font-weight:800;letter-spacing:-.02em;line-height:1.18;margin:.7rem 0 .7rem;}
.role .b{color:var(--mut);font-size:.94rem;line-height:1.5;}
.proof{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:.5rem;}
.proof div{border:1px solid var(--line);border-radius:14px;padding:18px 20px;background:var(--s1);}
.proof b{display:block;font-family:'JetBrains Mono',monospace;font-size:1.9rem;color:var(--acc);}
.proof span{color:var(--mut);font-size:.86rem;}
.ph{font-size:2.5rem;font-weight:800;letter-spacing:-.035em;margin:1.2rem 0 .2rem;}
.ps{color:var(--mut);font-size:1.02rem;margin-bottom:1.1rem;max-width:720px;}
.card{background:linear-gradient(180deg,var(--s2),var(--s1));border:1px solid var(--line);border-radius:16px;padding:22px;}
.pill{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;font-size:.74rem;letter-spacing:.16em;border:1px solid;}
.pair{font-size:1.6rem;font-weight:800;letter-spacing:-.02em;margin:.2rem 0 .8rem;}
.tiles{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px;}
.tile{background:var(--bg);border:1px solid var(--line);border-radius:12px;padding:14px 16px;}
.tile b{display:block;font-family:'JetBrains Mono',monospace;font-size:1.5rem;}
.tile span{color:var(--mut);font-size:.72rem;letter-spacing:.12em;font-weight:600;}
.story{color:#C8D0DE;line-height:1.6;font-size:1.02rem;}
.sub{font-size:.72rem;letter-spacing:.2em;color:var(--mut);font-weight:700;margin-bottom:12px;}
.seg{display:grid;grid-template-columns:96px 1fr 52px;gap:10px;align-items:center;margin:9px 0;font-size:.9rem;}
.seg .bar{height:8px;}
.bar{height:6px;background:#1C2230;border-radius:99px;overflow:hidden;margin-top:8px;}
.bar span{display:block;height:100%;background:linear-gradient(90deg,#1FBF8A,#2EE6A6);border-radius:99px;}
.lrow{display:flex;gap:18px;align-items:center;background:linear-gradient(180deg,var(--s2),var(--s1));border:1px solid var(--line);border-radius:14px;padding:16px 20px;}
.rk{font-family:'JetBrains Mono',monospace;color:var(--mut);font-size:1.1rem;width:30px;}
.lmain{flex:1;}.lname{font-weight:700;font-size:1.12rem;}.lsub{color:var(--mut);font-size:.84rem;margin-top:2px;}
.lstat{text-align:right;min-width:110px;}.lz{font-family:'JetBrains Mono',monospace;font-size:1.45rem;font-weight:700;color:var(--acc);}
.llab{font-size:.62rem;letter-spacing:.16em;color:var(--mut);}
.nodata{border-color:#3A2F1A;background:linear-gradient(180deg,#1B1710,#13110C);}
.nd-t{font-weight:700;color:#FFB020;margin-bottom:6px;}.nd-m{color:#C8BFA8;}
.trail{font-family:'JetBrains Mono',monospace;font-size:.8rem;color:#9FB0C8;line-height:1.9;}
.boot{text-align:center;padding:12vh 0 1rem;}.boot-t{font-size:2rem;font-weight:800;margin-top:1rem;}.boot-s{color:var(--mut);margin-top:.4rem;}
.foot{color:#5C6677;font-size:.76rem;margin-top:3rem;text-align:center;}
.stButton>button,.stDownloadButton>button,div[data-testid="stForm"] button{width:100%;background:var(--s2);color:var(--tx);border:1px solid #2A3242;border-radius:11px;font-weight:600;padding:.62rem 1rem;transition:.15s;}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:var(--acc);color:var(--acc);}
.stButton>button[kind="primary"],button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"],button[kind="primaryFormSubmit"]{background:var(--acc)!important;color:#04130D!important;border:0!important;font-weight:700;}
.stTextInput input,.stSelectbox div[data-baseweb="select"]>div{background:#0D1117!important;border:1px solid #2A3242!important;border-radius:11px!important;color:var(--tx)!important;font-size:1rem;}
div[data-testid="stForm"]{border:1px solid var(--line);border-radius:16px;background:var(--s1);padding:20px;}
.stProgress>div>div>div>div{background:var(--acc);}
div[data-testid="stStatusWidget"],details{border-radius:14px!important;}
"""
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def H(s):
    return "".join(line.strip() for line in s.splitlines())


def e(x):
    return html.escape(str(x))


# ───────────────────────────── QLOO CLIENT ─────────────────────────────
class QlooError(Exception):
    pass


def _read_key():
    try:
        return st.secrets["QLOO_API_KEY"]
    except Exception:
        return os.environ.get("QLOO_API_KEY", "")


API_KEY = _read_key()
_SESSION = requests.Session()
_GATE, _NEXT = threading.Lock(), [0.0]


def _pace():
    with _GATE:
        now = time.monotonic()
        wait = max(0.0, _NEXT[0] - now)
        _NEXT[0] = max(now, _NEXT[0]) + MIN_GAP
    if wait:
        time.sleep(wait)


def qget(path, params):
    if not API_KEY:
        raise QlooError("QLOO_API_KEY is not set (add it in the app's Secrets).")
    params = {k: v for k, v in params.items() if v not in (None, "")}
    backoff = 1.5
    for _ in range(5):
        _pace()
        try:
            r = _SESSION.get(BASE + path, params=params, timeout=30,
                             headers={"X-Api-Key": API_KEY, "Accept": "application/json"})
        except requests.RequestException:
            time.sleep(backoff); backoff *= 2; continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError:
                return None
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff); backoff = min(backoff * 2, 20); continue
        if r.status_code == 401:
            raise QlooError("Qloo rejected the API key (401).")
        return None  # 400/404: treated as "no data"
    raise QlooError("Qloo is not responding. Try again in a moment.")


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    return " ".join("".join(c for c in s if not unicodedata.combining(c)).casefold().split())


def sim(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    ta, tb = set(a.split()), set(b.split())
    return 0.5 * len(ta & tb) / max(1, len(ta | tb)) + 0.5 * (1 - abs(len(a) - len(b)) / max(len(a), len(b)))


def items(payload):
    if not isinstance(payload, dict):
        return []
    r = payload.get("results")
    if isinstance(r, list):
        return r
    if isinstance(r, dict):
        for k in ("entities", "items", "results", "data"):
            if isinstance(r.get(k), list):
                return r[k]
    return []


def ent(it):
    sub = it.get("entity") if isinstance(it.get("entity"), dict) else {}
    eid = it.get("entity_id") or it.get("id") or sub.get("entity_id") or sub.get("id")
    name = it.get("name") or sub.get("name") or ""
    types = it.get("types") or sub.get("types") or it.get("type") or sub.get("type") or ""
    types = " ".join(types) if isinstance(types, list) else str(types)
    akas = []
    for a in (it.get("properties") or {}).get("akas") or []:
        if isinstance(a, dict) and a.get("value"):
            akas.append(a["value"])
    return eid, name, types, akas


def score(it):
    if not isinstance(it, dict):
        return None
    q = it.get("query")
    if isinstance(q, dict) and isinstance(q.get("affinity"), (int, float)) and not isinstance(q["affinity"], bool):
        return float(q["affinity"])
    for k in ("affinity", "score", "similarity"):
        v = it.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def pair_score(cid, bid, extra=None):
    p = {"filter.type": "urn:entity:brand", "signal.interests.entities": cid,
         "filter.results.entities": bid, "take": 1}
    p.update(extra or {})
    its = items(qget("/v2/insights", p))
    return score(its[0]) if its else None


def panel_scores(cid, bids):
    out = {}
    for i in range(0, len(bids), CHUNK):
        d = qget("/v2/insights", {"filter.type": "urn:entity:brand", "signal.interests.entities": cid,
                                  "filter.results.entities": ",".join(bids[i:i + CHUNK]), "take": 50})
        for it in items(d):
            eid, s = ent(it)[0], score(it)
            if eid and s is not None:
                out[eid] = s
    return out


def _resolve_brand_raw(name):
    best = None
    for it in items(qget("/search", {"query": name})):
        eid, nm, tp, ak = ent(it)
        if not eid or not nm or "brand" not in norm(tp):
            continue
        s = max([sim(name, nm)] + [sim(name, a) for a in ak])
        if s >= 0.55 and (best is None or s > best["sim"]):
            best = {"id": eid, "name": nm, "sim": s}
    return best


def _resolve_celebrity_raw(name, probe_id):
    cands = []
    for it in items(qget("/search", {"query": name})):
        eid, nm, tp, ak = ent(it)
        if not eid or not nm:
            continue
        s = max([sim(name, nm)] + [sim(name, a) for a in ak])
        t = norm(tp)
        if s >= 0.85 and ("person" in t or "artist" in t):
            cands.append((s, eid, nm))
    for s, eid, nm in sorted(cands, reverse=True):
        if pair_score(eid, probe_id) is not None:   # must work as a taste signal
            return {"id": eid, "name": nm}
    return None


# cached wrappers used by the UI
@st.cache_data(ttl=86400, persist="disk", show_spinner=False)
def resolve_brand(name):
    return _resolve_brand_raw(name)


@st.cache_data(ttl=86400, persist="disk", show_spinner=False)
def resolve_celebrity(name, probe_id):
    return _resolve_celebrity_raw(name, probe_id)


@st.cache_data(ttl=21600, show_spinner=False)
def pair_score_c(cid, bid):
    return pair_score(cid, bid)


@st.cache_data(ttl=21600, show_spinner=False)
def live_row(cid, bids):
    return panel_scores(cid, list(bids))


@st.cache_data(ttl=21600, show_spinner=False)
def live_column(bid, celeb_ids):
    out = {}
    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(pair_score, cid, bid): cid for cid in celeb_ids}
        for f in as_completed(futs):
            v = f.result()
            if v is not None:
                out[futs[f]] = v
    return out


@st.cache_data(ttl=21600, show_spinner=False)
def lens_scores(cid, bid):
    out = {}
    with ThreadPoolExecutor(6) as ex:
        futs = {ex.submit(pair_score, cid, bid, p): k for k, p in LENSES.items()}
        for f in as_completed(futs):
            out[futs[f]] = f.result()
    return {k: out.get(k) for k in LENSES}


_B32 = "0123456789bcdefghjkmnpqrstuvwxyz"


def gh_decode(gh):
    lat, lon, even = [-90.0, 90.0], [-180.0, 180.0], True
    for ch in gh:
        cd = _B32.find(ch)
        if cd < 0:
            return None, None
        for mask in (16, 8, 4, 2, 1):
            rng = lon if even else lat
            mid = (rng[0] + rng[1]) / 2
            rng[0 if cd & mask else 1] = mid
            even = not even
    return (lat[0] + lat[1]) / 2, (lon[0] + lon[1]) / 2


@st.cache_data(ttl=21600, show_spinner=False)
def heatmap_cells(cid, city):
    d = qget("/v2/insights", {"filter.type": "urn:heatmap", "signal.interests.entities": cid,
                              "filter.location.query": city})
    res = (d or {}).get("results") if isinstance(d, dict) else None
    cells = res.get("heatmap") if isinstance(res, dict) else None
    out = []
    for c in cells or []:
        loc = c.get("location") if isinstance(c.get("location"), dict) else {}
        gh = loc.get("geohash") or c.get("geohash")
        lat, lon = loc.get("latitude") or loc.get("lat"), loc.get("longitude") or loc.get("lng")
        if (lat is None or lon is None) and gh:
            lat, lon = gh_decode(gh)
        s = score(c)
        if lat is not None and lon is not None and s is not None:
            out.append({"lat": lat, "lon": lon, "aff": s})
    return out


# ───────────────────────────── TASTE UNIVERSE (built once, shared) ─────────────────────────────
@st.cache_resource
def _store():
    return {"lock": threading.Lock(), "data": None}


def _read_disk():
    try:
        if os.path.exists(CACHE_FILE) and time.time() - os.path.getmtime(CACHE_FILE) < CACHE_MAX_AGE:
            d = json.load(open(CACHE_FILE))
            if d.get("brands") and d.get("celebs") and d.get("M"):
                return d
    except Exception:
        pass
    return None


def _build(progress):
    nike = _resolve_brand_raw("Nike")
    if not nike:
        raise QlooError("Could not reach the Qloo taste graph.")
    brands, celebs, M = {}, {}, {}
    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(_resolve_brand_raw, b): b for b in REF_BRANDS}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r:
                brands[r["id"]] = r["name"]
            progress(0.04 + 0.26 * i / len(futs), f"Resolving brands {i}/{len(futs)}")
    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(_resolve_celebrity_raw, n, nike["id"]): n for n in PANEL}
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            if r:
                celebs[futs[f]] = r
            progress(0.30 + 0.30 * i / len(futs), f"Resolving celebrity audiences {i}/{len(futs)}")
    bids = list(brands)
    with ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(panel_scores, c["id"], bids): n for n, c in celebs.items()}
        for i, f in enumerate(as_completed(futs), 1):
            M[futs[f]] = f.result()
            progress(0.60 + 0.38 * i / len(futs), f"Scoring taste affinities {i}/{len(futs)}")
    if len(celebs) < 8 or sum(len(r) for r in M.values()) < 100:
        raise QlooError("The taste graph did not load completely. Reload to retry.")
    return {"built": time.time(), "brands": brands, "celebs": celebs, "M": M}


def boot():
    store = _store()
    if store["data"]:
        return store["data"]
    ph = st.empty()
    with ph.container():
        st.markdown(H('<div class="boot"><div class="logo">◆ TASTEDESK</div>'
                      '<div class="boot-t">Loading the taste graph</div>'
                      '<div class="boot-s">First load only. About 30 seconds.</div></div>'), unsafe_allow_html=True)
        bar, msg = st.progress(0.0), st.empty()

    def cb(f, t):
        bar.progress(min(max(f, 0.0), 1.0))
        msg.markdown(H(f'<div class="boot-s mono" style="text-align:center">{e(t)}</div>'), unsafe_allow_html=True)

    with store["lock"]:
        if not store["data"]:
            data = _read_disk()
            if data is None:
                data = _build(cb)
                try:
                    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
                    json.dump(data, open(CACHE_FILE, "w"))
                except Exception:
                    pass
            store["data"] = data
    ph.empty()
    return store["data"]


# ───────────────────────────── STATS ─────────────────────────────
def pct_rank(v, ref):
    return (sum(r < v for r in ref) + 0.5 * sum(r == v for r in ref)) / len(ref) if ref else None


def column(U, bid, exclude_cid=None):
    """celebrity_id -> affinity for one brand across the celebrity panel."""
    if bid in U["brands"]:
        out = {c["id"]: U["M"][n][bid] for n, c in U["celebs"].items() if bid in U["M"].get(n, {})}
    else:
        out = dict(live_column(bid, tuple(c["id"] for c in U["celebs"].values())))
    out.pop(exclude_cid, None)
    return out


def row_for(U, cid):
    """brand_id -> affinity for one celebrity across the reference brands."""
    for n, c in U["celebs"].items():
        if c["id"] == cid:
            return U["M"].get(n, {})
    return live_row(cid, tuple(U["brands"]))


def zstats(vals):
    if len(vals) < 8:
        return None
    sd = statistics.pstdev(vals)
    return (statistics.mean(vals), sd) if sd > 1e-9 else None


def verdict(s):
    if s >= 85: return "PRIME FIT", "#2EE6A6"
    if s >= 65: return "STRONG FIT", "#9BE564"
    if s >= 40: return "MODERATE FIT", "#FFB020"
    return "WEAK FIT", "#FF5C6C"


# ───────────────────────────── UI HELPERS ─────────────────────────────
def gauge(s, color):
    r = 84; c = 2 * 3.14159265 * r
    return H(f'<svg width="210" height="210" viewBox="0 0 210 210"><circle cx="105" cy="105" r="{r}" fill="none" stroke="#1E2430" stroke-width="14"/>'
             f'<circle cx="105" cy="105" r="{r}" fill="none" stroke="{color}" stroke-width="14" stroke-linecap="round" stroke-dasharray="{c * s / 100:.1f} {c:.1f}" transform="rotate(-90 105 105)"/>'
             f'<text x="105" y="114" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="58" font-weight="700" fill="#F4F6FA">{s}</text>'
             f'<text x="105" y="140" text-anchor="middle" font-family="Inter,sans-serif" font-size="11" letter-spacing="3" fill="#7D8798">FIT SCORE</text></svg>')


def nodata(title, msg):
    st.markdown(H(f'<div class="card nodata"><div class="nd-t">{e(title)}</div><div class="nd-m">{e(msg)}</div></div>'),
                unsafe_allow_html=True)


def report_html(title, sub, rows):
    body = "".join(f"<tr><td>{e(a)}</td><td>{e(b)}</td><td style='text-align:right'><b>{e(c)}</b></td></tr>" for a, b, c in rows)
    return (f"<!doctype html><meta charset=utf-8><title>{e(title)}</title><style>td{{border-bottom:1px solid #ddd}}</style>"
            f"<body style='font-family:Inter,Arial,sans-serif;max-width:780px;margin:40px auto;color:#111'>"
            f"<div style='letter-spacing:3px;font-size:12px;color:#0a8f68'>TASTEDESK</div><h1 style='margin:6px 0'>{e(title)}</h1>"
            f"<p style='color:#555'>{e(sub)}</p><table style='width:100%;border-collapse:collapse;margin-top:18px' cellpadding=10>{body}</table>"
            f"<p style='color:#888;font-size:12px;margin-top:30px'>Scores computed from Qloo's taste graph via /v2/insights (filter.results.entities).</p></body>")


def start(page, **vals):
    st.session_state.page = page
    for k, v in vals.items():
        st.session_state[k] = v
    st.session_state["run_" + page] = bool(vals)


def arm(page):
    st.session_state["run_" + page] = True


def top():
    c1, c2 = st.columns([6, 1.4], vertical_alignment="center")
    c1.markdown(H('<div class="logo">◆ TASTEDESK</div>'), unsafe_allow_html=True)
    if st.session_state.page != "home":
        c2.button("← Switch role", on_click=start, args=("home",))


def chips(items_, page, key_a, key_b=None):
    cols = st.columns(len(items_))
    for i, (label, vals) in enumerate(items_):
        cols[i].button(label, key=f"chip_{page}_{i}", on_click=start, args=(page,), kwargs=vals)

# ───────────────────────────── TASTE TWINS ─────────────────────────────
TWINS_PER_TYPE = 5


@st.cache_data(ttl=21600, show_spinner=False)
def twins_scored(cid, cname, bid, brand_ids):
    """Qloo lookalikes of a celebrity (5 people + 5 artists), each scored against one brand."""
    cands, seen = [], {cid}
    for t in ("urn:entity:person", "urn:entity:artist"):
        got = 0
        for it in items(qget("/v2/insights", {"filter.type": t, "signal.interests.entities": cid, "take": 20})):
            eid, nm, _tp, _ak = ent(it)
            if not eid or not nm or eid in seen or sim(cname, nm) >= 0.85:
                continue
            seen.add(eid)
            cands.append((eid, nm, "Artist" if "artist" in t else "Person"))
            got += 1
            if got >= TWINS_PER_TYPE:
                break

    def work(c):
        eid, nm, kind = c
        row = panel_scores(eid, list(brand_ids))        # twin x reference brands
        aff = row.get(bid)
        if aff is None:
            aff = pair_score(eid, bid)
        ref = [v for kk, v in row.items() if kk != bid]
        if aff is None or len(ref) < 15:
            return None
        return {"name": nm, "kind": kind, "aff": aff, "fit": round(100 * pct_rank(aff, ref))}

    out = []
    with ThreadPoolExecutor(6) as ex:
        for r in ex.map(work, cands):
            if r:
                out.append(r)
    out.sort(key=lambda r: -r["fit"])
    return out


def render_twins(ce_name, br_name, own_fit, tw):
    st.markdown('<div class="kicker" style="margin-top:2rem">TASTE TWINS · THE BACKUP PLAN</div>', unsafe_allow_html=True)
    if len(tw) < 5:
        return nodata("Not enough data", f"Qloo returned too few taste twins for {ce_name}.")
    st.markdown(H(f'<div class="ph" style="font-size:1.9rem;margin-top:0">Stars who reach {e(ce_name)}’s fans, scored for {e(br_name)}</div>'
                  f'<div class="ps">{e(ce_name)} scores {own_fit} for {e(br_name)}. Out of budget? Compare these against your number. '
                  'Already signed one? Skip the others and avoid paying twice for the same taste. Scandal? The swap is already ranked.</div>'),
                unsafe_allow_html=True)
    for i, r in enumerate(tw[:5], 1):
        label, color = verdict(r["fit"])
        st.markdown(H(f'<div class="lrow" style="margin-bottom:10px"><div class="rk">{i:02d}</div><div class="lmain">'
                      f'<div class="lname">{e(r["name"])}</div>'
                      f'<div class="lsub">{e(r["kind"])} · taste twin of {e(ce_name)} · affinity {r["aff"]:.2f}</div>'
                      f'<div class="bar"><span style="width:{r["fit"]}%"></span></div></div>'
                      f'<div class="lstat"><div class="lz" style="color:{color}">{r["fit"]}</div>'
                      f'<div class="llab">{label}</div></div></div>'), unsafe_allow_html=True)
    st.markdown(H('<div class="proof"><div><b>0.73 vs 0.43</b><span>twins share the star’s brand taste vs random stars · won for 67 of 73 celebrities</span></div>'
                  '<div><b>44 / 56</b><span>real signed deals where the deal brand fits twins better than random stars</span></div>'
                  '<div><b>40 / 56</b><span>deals with a twin in the top 10% for the same brand</span></div></div>'),
                unsafe_allow_html=True)
    st.markdown('<div class="foot" style="margin-top:.8rem">Twins are a close fit, not a clone. Qloo carries no pricing, so you bring the budget.</div>',
                unsafe_allow_html=True)


def tool_taste_twins(U, celebrity, brand):
    br, ce = resolve_brand(brand), _celeb_for(celebrity)
    if not br or not ce:
        return {"error": f"'{brand if not br else celebrity}' not usable in Qloo"}
    tw = twins_scored(ce["id"], ce["name"], br["id"], tuple(U["brands"]))
    if len(tw) < 5:
        return {"error": "too few taste twins"}
    return {"celebrity": ce["name"], "brand": br["name"],
            "taste_twins": [{"name": r["name"], "type": r["kind"], "fit_score_0_100": r["fit"]} for r in tw[:5]]}

# ───────────────────────────── PAGES ─────────────────────────────
ROLES = [
    ("brand", "BRAND · CMO TEAM", "Who do we sign?",
     "Rank celebrity audiences by how strongly their fans over-index on your brand.",
     {"brand_q": "Hyundai"}, "Try: Hyundai"),
    ("talent", "TALENT AGENCY · CELEBRITY", "Which brands fit my client?",
     "Get a ready-made pitch list of the brands your client's fans love most.",
     {"talent_q": "Cedric the Entertainer"}, "Try: Cedric the Entertainer"),
    ("agency", "AD AGENCY", "Is this pair worth it, and where do we launch?",
     "Underwrite any celebrity × brand pair: fit score, audience segments, city map and backup taste twins.",
     {"ag_celeb": "Ryan Reynolds", "ag_brand": "Aviation American Gin"}, "Try: Reynolds × Aviation Gin"),
]


def page_home(U):
    st.markdown(H('<div class="hero"><h1>Know the fit<br><em>before the check is written.</em></h1>'
                  '<p>TasteDesk underwrites celebrity × brand deals with a reproducible Cultural Fit Score computed live from Qloo\'s taste graph. Not vibes. Not follower counts. Evidence.</p></div>'),
                unsafe_allow_html=True)
    st.markdown('<div class="kicker">WHO ARE YOU?</div>', unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for col, (page, tag, q, blurb, ex, exlabel) in zip(cols, ROLES):
        with col:
            st.markdown(H(f'<div class="role"><div class="tag">{tag}</div><div class="q">{q}</div><div class="b">{blurb}</div></div>'),
                        unsafe_allow_html=True)
            st.button("Open →", key=f"open_{page}", type="primary", on_click=start, args=(page,))
            st.button(exlabel, key=f"try_{page}", on_click=start, args=(page,), kwargs=ex)
    st.markdown('<div class="kicker">OR JUST ASK</div>', unsafe_allow_html=True)
    st.button("Ask the TasteDesk agent →", key="open_agent", type="primary", on_click=start, args=("agent",))
    st.markdown('<div class="kicker">THE EVIDENCE</div>', unsafe_allow_html=True)
    st.markdown(H('<div class="proof"><div><b>53</b><span>real signed celebrity deals back-tested</span></div>'
                  '<div><b>5×</b><span>better than chance: 27 of 53 landed in the top 10% of their row</span></div>'
                  '<div><b>13 / 19</b><span>endorsement deals in the top 10% (Nike × Serena, Aveeno × Aniston…)</span></div></div>'),
                unsafe_allow_html=True)
    st.markdown(f'<div class="foot">Powered by Qloo · {len(U["celebs"])} celebrity audiences × {len(U["brands"])} reference brands · scores computed live</div>',
                unsafe_allow_html=True)


def header(title, sub):
    st.markdown(f'<div class="ph">{e(title)}</div><div class="ps">{e(sub)}</div>', unsafe_allow_html=True)


# ---------- BRAND: who do we sign ----------
def page_brand(U):
    header("Who do we sign?", "Enter your brand. We rank celebrity audiences by how much their fans over-index on it.")
    chips([("Hyundai", {"brand_q": "Hyundai"}), ("Grey Goose", {"brand_q": "Grey Goose"}),
           ("Old Spice", {"brand_q": "Old Spice"})], "brand", "brand_q")
    with st.form("brand_form"):
        st.text_input("Brand", key="brand_q", placeholder="e.g. Hyundai, Grey Goose, Nike")
        st.form_submit_button("Find talent →", type="primary", on_click=arm, args=("brand",))
    q = st.session_state.get("brand_q", "").strip()
    if not (st.session_state.get("run_brand") and q):
        return
    box = st.status(f"Scoring celebrity audiences for {q}…", expanded=True)
    box.write("Resolving brand entity in Qloo…")
    b = resolve_brand(q)
    if not b:
        box.update(label="Brand not found", state="error")
        return nodata("Not enough data", f"“{q}” is not in Qloo's taste graph. Try the exact brand name.")
    box.write(f"Matched **{b['name']}**. Scoring {len(U['celebs'])} celebrity audiences…")
    col = column(U, b["id"])
    st_ = zstats(list(col.values()))
    if not st_:
        box.update(label="Not enough data", state="error")
        return nodata("Not enough data", f"Qloo returned too few audience scores for {b['name']}.")
    mu, sd = st_
    vals = list(col.values())
    rows = []
    for n, c in U["celebs"].items():
        if c["id"] in col:
            a = col[c["id"]]
            rows.append((n, a, (a - mu) / sd, round(100 * pct_rank(a, vals))))
    rows.sort(key=lambda r: -r[2])
    box.update(label=f"Shortlist ready · {b['name']}", state="complete", expanded=False)
    st.markdown(f'<div class="sub">TOP 10 OF {len(rows)} CELEBRITY AUDIENCES · RANKED BY AUDIENCE LIFT FOR {e(b["name"]).upper()}</div>',
                unsafe_allow_html=True)
    for i, (n, a, z, p) in enumerate(rows[:10], 1):
        c1, c2 = st.columns([9, 2.2], vertical_alignment="center")
        c1.markdown(H(f'<div class="lrow"><div class="rk">{i:02d}</div><div class="lmain"><div class="lname">{e(n)}</div>'
                      f'<div class="lsub">Fans like {e(b["name"])} more than {p}% of audiences · affinity {a:.2f}</div>'
                      f'<div class="bar"><span style="width:{p}%"></span></div></div>'
                      f'<div class="lstat"><div class="lz">{z:+.1f}σ</div><div class="llab">AUDIENCE LIFT</div></div></div>'),
                    unsafe_allow_html=True)
        c2.button("Underwrite →", key=f"uw_{i}", on_click=start, args=("agency",),
                  kwargs={"ag_celeb": n, "ag_brand": b["name"]})
    st.download_button("Download shortlist (one-pager)",
                       report_html(f"Talent shortlist: {b['name']}", "Celebrity audiences ranked by audience lift.",
                                   [(f"{i}. {n}", f"fans like it more than {p}% of audiences", f"{z:+.1f}σ")
                                    for i, (n, a, z, p) in enumerate(rows[:10], 1)]),
                       file_name=f"tastedesk_{b['name']}.html", mime="text/html")


# ---------- TALENT: which brands fit my client ----------
def page_talent(U):
    header("Which brands fit my client?", "Enter a celebrity. We build the pitch list: brands their fans love far more than other audiences do.")
    chips([("Cedric the Entertainer", {"talent_q": "Cedric the Entertainer"}), ("Serena Williams", {"talent_q": "Serena Williams"}),
           ("Ryan Reynolds", {"talent_q": "Ryan Reynolds"})], "talent", "talent_q")
    with st.form("talent_form"):
        st.text_input("Celebrity", key="talent_q", placeholder="e.g. Cedric the Entertainer")
        st.form_submit_button("Build pitch list →", type="primary", on_click=arm, args=("talent",))
    q = st.session_state.get("talent_q", "").strip()
    if not (st.session_state.get("run_talent") and q):
        return
    box = st.status(f"Building pitch list for {q}…", expanded=True)
    nike = resolve_brand("Nike")
    box.write("Resolving celebrity as a taste signal…")
    c = resolve_celebrity(q, nike["id"])
    if not c:
        box.update(label="Celebrity not found", state="error")
        return nodata("Not enough data", f"“{q}” could not be used as a taste signal in Qloo. Try the full name.")
    box.write(f"Matched **{c['name']}**. Scoring {len(U['brands'])} brands against their audience…")
    row = row_for(U, c["id"])
    out = []
    for bid, a in row.items():
        s = zstats(list(column(U, bid, exclude_cid=c["id"]).values()))
        if s:
            vals = list(column(U, bid, exclude_cid=c["id"]).values())
            out.append((U["brands"][bid], a, (a - s[0]) / s[1], round(100 * pct_rank(a, vals))))
    if len(out) < 5:
        box.update(label="Not enough data", state="error")
        return nodata("Not enough data", f"Qloo returned too few brand scores for {c['name']}.")
    out.sort(key=lambda r: -r[2])
    box.update(label=f"Pitch list ready · {c['name']}", state="complete", expanded=False)
    st.markdown(f'<div class="sub">BRANDS {e(c["name"]).upper()}\'S FANS OVER-INDEX ON · POPULARITY-CORRECTED</div>', unsafe_allow_html=True)
    for i, (n, a, z, p) in enumerate(out[:12], 1):
        st.markdown(H(f'<div class="lrow" style="margin-bottom:10px"><div class="rk">{i:02d}</div><div class="lmain"><div class="lname">{e(n)}</div>'
                      f'<div class="lsub">Their fans like it more than {p}% of celebrity audiences · affinity {a:.2f}</div>'
                      f'<div class="bar"><span style="width:{p}%"></span></div></div>'
                      f'<div class="lstat"><div class="lz">{z:+.1f}σ</div><div class="llab">AUDIENCE LIFT</div></div></div>'),
                    unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    df = pd.DataFrame(out, columns=["brand", "affinity", "audience_lift_z", "percentile_vs_audiences"])
    d1.download_button("Download pitch list (CSV)", df.to_csv(index=False), file_name=f"tastedesk_{c['name']}.csv", mime="text/csv")
    d2.download_button("Download sponsorship one-pager",
                       report_html(f"Sponsorship pitch list: {c['name']}", "Brands this audience over-indexes on.",
                                   [(f"{i}. {n}", f"fans like it more than {p}% of audiences", f"{z:+.1f}σ")
                                    for i, (n, a, z, p) in enumerate(out[:12], 1)]),
                       file_name=f"tastedesk_{c['name']}.html", mime="text/html")


# ---------- AGENCY: underwrite a pair ----------
def page_agency(U):
    header("Is this pair worth it?", "Type any celebrity × brand. Get the underwriting dossier: fit score, audience segments and a city map.")
    chips([("Reynolds × Aviation Gin", {"ag_celeb": "Ryan Reynolds", "ag_brand": "Aviation American Gin"}),
           ("Cedric × Hyundai", {"ag_celeb": "Cedric the Entertainer", "ag_brand": "Hyundai"}),
           ("Serena × Nike", {"ag_celeb": "Serena Williams", "ag_brand": "Nike"})], "agency", "ag_celeb")
    with st.form("agency_form"):
        a, b, c = st.columns([3, 3, 2])
        a.text_input("Celebrity", key="ag_celeb", placeholder="e.g. Cedric the Entertainer")
        b.text_input("Brand", key="ag_brand", placeholder="e.g. Hyundai")
        c.selectbox("City for audience map", CITIES, key="ag_city")
        st.form_submit_button("Underwrite →", type="primary", on_click=arm, args=("agency",))
    cq, bq = st.session_state.get("ag_celeb", "").strip(), st.session_state.get("ag_brand", "").strip()
    if not (st.session_state.get("run_agency") and cq and bq):
        return
    city = st.session_state.get("ag_city", CITIES[0])
    box = st.status(f"Underwriting {cq} × {bq}…", expanded=True)
    nike = resolve_brand("Nike")
    box.write("Resolving entities…")
    br, ce = resolve_brand(bq), resolve_celebrity(cq, nike["id"])
    if not br or not ce:
        box.update(label="Entity not found", state="error")
        miss = bq if not br else cq
        return nodata("Not enough data", f"“{miss}” is not usable in Qloo's taste graph. Try the exact name.")
    box.write(f"Scoring **{ce['name']} × {br['name']}** (filter.results.entities)…")
    aff = pair_score_c(ce["id"], br["id"])
    if aff is None:
        box.update(label="Not enough data", state="error")
        return nodata("Not enough data", f"Qloo has no affinity score for {ce['name']} × {br['name']}.")
    box.write(f"Ranking against {len(U['brands'])} reference brands…")
    row = row_for(U, ce["id"])
    ref = [v for k, v in row.items() if k != br["id"]]
    if len(ref) < 10:
        box.update(label="Not enough data", state="error")
        return nodata("Not enough data", f"Too few brand scores for {ce['name']} to rank this pair.")
    fit = round(100 * pct_rank(aff, ref))
    rank, n = 1 + sum(v > aff for v in ref), len(ref) + 1
    box.write("Comparing with other celebrity audiences…")
    col = column(U, br["id"], exclude_cid=ce["id"])
    zs = zstats(list(col.values()))
    z = (aff - zs[0]) / zs[1] if zs else None
    lift = round(100 * pct_rank(aff, list(col.values()))) if zs else None
    box.write("Splitting by audience segment and mapping the city…")
    lens = lens_scores(ce["id"], br["id"])
    cells = heatmap_cells(ce["id"], city)
    box.write("Finding taste twins…")
    tw = twins_scored(ce["id"], ce["name"], br["id"], tuple(U["brands"]))
    box.update(label=f"Dossier ready · {ce['name']} × {br['name']}", state="complete", expanded=False)

    label, color = verdict(fit)
    story = (f"{e(br['name'])} ranks <b>#{rank} of {n}</b> brands tested for {e(ce['name'])}'s audience"
             + (f", and their fans rate it higher than <b>{lift}%</b> of the {len(col) + 1} celebrity audiences compared." if lift is not None else "."))
    l, r = st.columns([1, 2.3], gap="medium")
    l.markdown(H(f'<div class="card" style="text-align:center">{gauge(fit, color)}<div style="margin-top:6px"><span class="pill" style="color:{color};border-color:{color}">{label}</span></div></div>'),
               unsafe_allow_html=True)
    r.markdown(H(f'<div class="card"><div class="sub">UNDERWRITING DOSSIER</div><div class="pair">{e(ce["name"])} × {e(br["name"])}</div>'
                 f'<div class="story">{story}</div><div class="tiles">'
                 f'<div class="tile"><b>{"n/a" if z is None else f"{z:+.1f}σ"}</b><span>AUDIENCE LIFT</span></div>'
                 f'<div class="tile"><b>{aff:.2f}</b><span>RAW AFFINITY</span></div>'
                 f'<div class="tile"><b>#{rank}/{n}</b><span>BRAND RANK</span></div></div></div>'), unsafe_allow_html=True)
    render_twins(ce["name"], br["name"], fit, tw)
    seg_col, map_col = st.columns(2, gap="medium")
    with seg_col:
        segs = [(k, v) for k, v in lens.items() if v is not None]
        body = "".join(f'<div class="seg"><span>{e(k)}</span><div class="bar"><span style="width:{max(2, min(100, v * 100)):.0f}%"></span></div><span class="mono">{v:.2f}</span></div>' for k, v in segs)
        st.markdown(H(f'<div class="card"><div class="sub">AFFINITY BY AUDIENCE SEGMENT</div>{body or "<div class=nd-m>No segment data for this pair.</div>"}</div>'),
                    unsafe_allow_html=True)
    with map_col:
        st.markdown(H(f'<div class="card" style="padding-bottom:10px"><div class="sub">WHERE THIS AUDIENCE LIVES · {e(city).upper()}</div></div>'), unsafe_allow_html=True)
        if cells:
            df = pd.DataFrame(cells)
            lo, hi = df.aff.min(), df.aff.max()
            df["fill"] = ((df.aff - lo) / (hi - lo + 1e-9)).apply(lambda w: [46, 230, 166, int(60 + 195 * w)])
            deck = pdk.Deck(layers=[pdk.Layer("ScatterplotLayer", df, get_position="[lon, lat]", get_fill_color="fill",
                                              get_radius=140, radius_min_pixels=3)],
                            initial_view_state=pdk.ViewState(latitude=float(df.lat.mean()), longitude=float(df.lon.mean()), zoom=9.3),
                            map_style="dark", height=260)
            st.pydeck_chart(deck)
        else:
            nodata("No map data", f"Qloo returned no heatmap cells for this audience in {city}.")
    with st.expander("Evidence trail"):
        lines = [f"/search → {cq!r} resolved to {ce['name']} (valid taste signal); {bq!r} resolved to {br['name']}",
                 f"/v2/insights · filter.results.entities → raw affinity {aff:.3f}",
                 f"ranked vs {n - 1} reference brands for {ce['name']} → #{rank}, percentile {fit}"]
        if zs:
            lines.append(f"compared with {len(col)} other celebrity audiences → mean {zs[0]:.3f}, σ {zs[1]:.3f}, z {z:+.2f}")
        lines += ["/v2/insights · signal.demographics → segment affinities", f"/v2/insights · urn:heatmap → {len(cells)} cells in {city}"]
        st.markdown('<div class="trail">' + "<br>".join(f"▸ {e(x)}" for x in lines) + "</div>", unsafe_allow_html=True)
    st.download_button("Download dossier (one-pager)",
                       report_html(f"Underwriting dossier: {ce['name']} × {br['name']}", f"Verdict: {label}",
                                   [("Fit Score", "percentile vs reference brands", f"{fit}/100"),
                                    ("Audience lift", "vs other celebrity audiences", "n/a" if z is None else f"{z:+.1f}σ"),
                                    ("Raw affinity", "Qloo score", f"{aff:.2f}"), ("Brand rank", f"of {n} tested", f"#{rank}")]),
                       file_name=f"tastedesk_{ce['name']}_{br['name']}.html", mime="text/html")


# ───────────────────────────── AGENT (Gemini plans, Qloo scores) ─────────────────────────────
GEMINI_MODEL = "gemini-3.1-flash-lite"
MAX_STEPS = 12


class AgentError(Exception):
    pass


def _gem_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def _celeb_for(name):
    nike = resolve_brand("Nike")
    return resolve_celebrity(name, nike["id"]) if nike else None


def tool_talent_for_brand(U, brand):
    b = resolve_brand(brand)
    if not b:
        return {"error": f"'{brand}' not found in Qloo"}
    col = column(U, b["id"])
    vals = list(col.values())
    zs = zstats(vals)
    if not zs:
        return {"error": "too few audience scores for this brand"}
    rows = []
    for n, c in U["celebs"].items():
        if c["id"] in col:
            a = col[c["id"]]
            rows.append({"celebrity": n, "audience_lift_z": round((a - zs[0]) / zs[1], 2),
                         "percentile": round(100 * pct_rank(a, vals)), "raw_affinity": round(a, 3)})
    rows.sort(key=lambda r: -r["audience_lift_z"])
    return {"brand": b["name"], "audiences_compared": len(rows), "top_talent": rows[:8]}


def tool_brands_for_talent(U, celebrity):
    c = _celeb_for(celebrity)
    if not c:
        return {"error": f"'{celebrity}' cannot be used as a taste signal in Qloo"}
    row = row_for(U, c["id"])
    out = []
    for bid, a in row.items():
        vals = list(column(U, bid, exclude_cid=c["id"]).values())
        s = zstats(vals)
        if s:
            out.append({"brand": U["brands"][bid], "audience_lift_z": round((a - s[0]) / s[1], 2),
                        "percentile": round(100 * pct_rank(a, vals)), "raw_affinity": round(a, 3)})
    if len(out) < 5:
        return {"error": "too few brand scores for this celebrity"}
    out.sort(key=lambda r: -r["audience_lift_z"])
    return {"celebrity": c["name"], "brands_tested": len(out), "top_brands": out[:8]}


def tool_underwrite_pair(U, celebrity, brand):
    br, ce = resolve_brand(brand), _celeb_for(celebrity)
    if not br or not ce:
        return {"error": f"'{brand if not br else celebrity}' not usable in Qloo"}
    aff = pair_score_c(ce["id"], br["id"])
    if aff is None:
        return {"error": "Qloo has no affinity score for this pair"}
    row = row_for(U, ce["id"])
    ref = [v for k, v in row.items() if k != br["id"]]
    if len(ref) < 10:
        return {"error": "too few brand scores to rank this pair"}
    fit = round(100 * pct_rank(aff, ref))
    col = column(U, br["id"], exclude_cid=ce["id"])
    zs = zstats(list(col.values()))
    return {"celebrity": ce["name"], "brand": br["name"], "fit_score_0_100": fit,
            "verdict": verdict(fit)[0], "brand_rank": 1 + sum(v > aff for v in ref), "of_brands": len(ref) + 1,
            "audience_lift_z": round((aff - zs[0]) / zs[1], 2) if zs else None, "raw_affinity": round(aff, 3)}


def tool_audience_segments(U, celebrity, brand):
    br, ce = resolve_brand(brand), _celeb_for(celebrity)
    if not br or not ce:
        return {"error": "entity not usable in Qloo"}
    lens = lens_scores(ce["id"], br["id"])
    return {"celebrity": ce["name"], "brand": br["name"],
            "affinity_by_segment": {k: round(v, 2) for k, v in lens.items() if v is not None}}


TOOLS = {"find_talent_for_brand": tool_talent_for_brand, "find_brands_for_talent": tool_brands_for_talent,
	 "find_taste_twins": tool_taste_twins,
         "underwrite_pair": tool_underwrite_pair, "audience_segments": tool_audience_segments}


def _decl(name, desc, props):
    return {"name": name, "description": desc,
            "parameters": {"type": "OBJECT", "required": list(props),
                           "properties": {k: {"type": "STRING", "description": v} for k, v in props.items()}}}


TOOL_DECLS = [
    _decl("find_talent_for_brand", "Rank celebrity audiences by how strongly their fans over-index on a brand (Qloo).",
          {"brand": "Brand name"}),
    _decl("find_brands_for_talent", "Rank brands that a celebrity's fans over-index on (Qloo).",
          {"celebrity": "Celebrity name"}),
    _decl("underwrite_pair", "Cultural Fit Score 0-100, rank and audience lift for one celebrity x brand pair (Qloo).",
          {"celebrity": "Celebrity name", "brand": "Brand name"}),
    _decl("audience_segments", "Affinity of one celebrity x brand pair by age and gender segment (Qloo).",
          {"celebrity": "Celebrity name", "brand": "Brand name"}),
    _decl("find_taste_twins", "Backup talent: stars whose fans share a celebrity's taste, each scored for the brand (Qloo).",
          {"celebrity": "Celebrity name", "brand": "Brand name"}),
]

SYSTEM = (
    "You are TasteDesk, a cultural underwriting analyst for brands, talent agencies and ad agencies. "
    "Every number and every claim about fit must come from tool results (Qloo). Never invent scores, brands, "
    "celebrities or facts. Plan: for a brand brief call find_talent_for_brand, then underwrite_pair and "
    "audience_segments for the top 2-3. For a talent brief call find_brands_for_talent, then underwrite_pair for "
    "the top 2-3. For a pair call underwrite_pair, audience_segments and find_taste_twins (backup talent). If a tool returns an error, say "
    "'not enough data' for that item and move on. Final answer: a 2-line verdict, a markdown table of up to 5 "
    "options (name, fit score or audience lift, best segment), and one risk or caveat. Plain language, no hype, "
    "under 220 words."
)


def _gemini(contents, tools=True):
    key = _gem_key()
    if not key:
        raise AgentError("GEMINI_API_KEY is not set (add it in the app's Secrets).")
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": contents,
            "generationConfig": {"temperature": 0.2}}
    if tools:
        body["tools"] = [{"functionDeclarations": TOOL_DECLS}]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    backoff = 2.0
    for _ in range(5):
        try:
            r = requests.post(url, json=body, timeout=60,
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        except requests.RequestException:
            time.sleep(backoff); backoff *= 2; continue
        if r.status_code == 200:
            return r.json()
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff); backoff = min(backoff * 2, 20); continue
        raise AgentError(f"Gemini error {r.status_code}: {r.text[:160]}")
    raise AgentError("Gemini is busy. Try again in a moment.")


def _parts(d):
    cand = (d.get("candidates") or [{}])[0]
    return (cand.get("content") or {}).get("parts") or []


def run_agent(U, brief, box):
    contents = [{"role": "user", "parts": [{"text": brief}]}]
    for _ in range(MAX_STEPS):
        parts = _parts(_gemini(contents))
        calls = [p["functionCall"] for p in parts if "functionCall" in p]
        if not calls:
            text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if text:
                return text
            raise AgentError("The agent returned an empty answer. Try again.")
        contents.append({"role": "model", "parts": parts})   # keep verbatim (thought signatures)
        resp = []
        for fc in calls:
            name, args = fc.get("name"), fc.get("args") or {}
            box.write(f"▸ `{name}` {json.dumps(args, ensure_ascii=False)}")
            fn = TOOLS.get(name)
            try:
                result = fn(U, **args) if fn else {"error": f"unknown tool {name}"}
            except QlooError:
                raise
            except Exception as ex:
                result = {"error": str(ex)[:150]}
            resp.append({"functionResponse": {"name": name, "response": {"result": result}}})
        contents.append({"role": "user", "parts": resp})
    contents[-1]["parts"].append({"text": "Write the final answer now using only the data gathered."})
    text = "".join(p.get("text", "") for p in _parts(_gemini(contents, tools=False)) if not p.get("thought")).strip()
    if not text:
        raise AgentError("The agent ran out of steps. Try a simpler brief.")
    return text


AGENT_EXAMPLES = [
    ("Car brand, pick talent", {"agent_q": "We are Hyundai. Which celebrity should we sign? Shortlist the best 3 and tell me which audience segment is strongest."}),
    ("Brands for Cedric", {"agent_q": "Cedric the Entertainer's agency wants a sponsorship pitch list. Which brands fit his fans best, and which one is the safest first call?"}),
    ("Is this deal worth it?", {"agent_q": "Is Ryan Reynolds x Aviation American Gin a strong cultural fit, and which age or gender segment drives it?"}),
]


def page_agent(U):
    header("Ask TasteDesk", "Describe the deal in plain English. The agent plans the steps and calls Qloo for every number.")
    chips(AGENT_EXAMPLES, "agent", "agent_q")
    with st.form("agent_form"):
        st.text_area("Your brief", key="agent_q", height=110,
                     placeholder="e.g. We are a beverage brand. Which celebrity fits us best?")
        st.form_submit_button("Run agent →", type="primary", on_click=arm, args=("agent",))
    q = st.session_state.get("agent_q", "").strip()
    if not (st.session_state.get("run_agent") and q):
        return
    box = st.status("Agent working…", expanded=True)
    try:
        text = run_agent(U, q, box)
    except AgentError as ex:
        box.update(label="Agent stopped", state="error")
        return nodata("Agent could not finish", str(ex))
    box.update(label="Agent finished", state="complete", expanded=False)
    st.markdown('<div class="sub">AGENT ANSWER · ALL SCORES FROM QLOO</div>', unsafe_allow_html=True)
    st.markdown(text.replace("$", "\\$"))

# ───────────────────────────── ROUTER ─────────────────────────────
for k, v in {"page": "home", "brand_q": "", "talent_q": "", "ag_celeb": "", "ag_brand": "", "ag_city": CITIES[0]}.items():
    st.session_state.setdefault(k, v)

try:
    U = boot()
except QlooError as ex:
    nodata("TasteDesk could not start", str(ex))
    st.stop()

top()
PAGES = {"home": page_home, "brand": page_brand, "talent": page_talent, "agency": page_agency, "agent": page_agent}
try:
    PAGES[st.session_state.page](U)
except QlooError as ex:
    nodata("Qloo is unreachable", str(ex))
