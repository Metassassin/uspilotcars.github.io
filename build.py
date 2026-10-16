#!/usr/bin/env python3
"""
US Pilot Cars — static site builder.

Reads the data files in /data and the small set of templates below, and
writes plain HTML into the repository root so the whole thing can be served
by GitHub Pages with no build step at request time.

Run it with:  python3 build.py
Re-run it any time you edit a file under /data (add an advertiser, add a
state's regulations, etc.) and commit the regenerated HTML.

No third-party dependencies. Python 3.8+ standard library only.
"""
import json
import os
import shutil
from html.parser import HTMLParser
from datetime import date
import re
import html
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

SITE_NAME = "US Pilot Cars"
SITE_TAGLINE = "Pilot Car & Escort Vehicle Directory"
SITE_URL = os.environ.get("SITE_URL", "https://uspilotcars.com").rstrip("/")

# Everything the website serves is written here. Cloudflare Pages publishes
# this folder. Source files (build.py, data/, docs) stay out of it, so they
# are never served to visitors.
OUT = os.path.join(ROOT, "dist")

# ---------------------------------------------------------------- load data
with open(os.path.join(DATA, "states.json")) as f:
    STATES = json.load(f)
CONTENT = os.path.join(ROOT, "content")


def load_folder(folder):
    """Read every .json file in a content folder (one file per business).

    These files are written by Pages CMS when grandma clicks Save. A file
    that can't be read is SKIPPED WITH A WARNING rather than stopping the
    build -- one bad entry must never prevent every other change from
    going live.
    """
    items = []
    path = os.path.join(CONTENT, folder)
    if not os.path.isdir(path):
        return items
    for fn in sorted(os.listdir(path)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(path, fn), encoding="utf-8") as f:
                item = json.load(f)
            if not isinstance(item, dict):
                raise ValueError("not a single entry")
            item["_file"] = fn
            items.append(item)
        except Exception as e:
            print(f"  WARNING: skipped content/{folder}/{fn} ({e})")
    return items


def as_list(v):
    """Form fields can arrive as a list, a single string, or empty."""
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return [x for x in v if x]


def clean_url(u):
    """People type 'na-pcs.com' -- make it a working link."""
    u = (u or "").strip()
    if u and not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u


# Accept either the internal code ("super_listing") or the words shown in
# the editor ("Super listing (large box with picture)"). Editors and form
# tools don't always store what you expect; the site should understand both.
TIER_WORDS = [            # checked in order -- most specific first
    ("sitewide", "global_banner"), ("global", "global_banner"),
    ("state banner", "state_banner"), ("banner", "state_banner"),
    ("super", "super_listing"), ("bold", "bold_listing"), ("basic", "basic_listing"),
]


def normalize_tier(value, fn):
    v = (value or "").strip()
    if v in TIER_ORDER:
        return v
    low = v.lower().replace("_", " ")
    for word, tier in TIER_WORDS:
        if word in low:
            return tier
    if v:
        print(f"  WARNING: content/listings/{fn}: unrecognised ad package {v!r} -- showing it as a basic listing")
    return "basic_listing"


def region_lookup():
    with open(os.path.join(DATA, "states.json")) as f:
        s = json.load(f)
    table = {"sitewide": "sitewide", "every page of the site": "sitewide",
             "★ every page of the site": "sitewide", "every page": "sitewide"}
    for r in s["us_states"] + s["ca_provinces"]:
        for key in (r["slug"], r["name"], r["name"] + " (Canada)",
                    r["slug"].replace("-", "_"), r["slug"].replace("-", " ")):
            table[key.lower()] = r["slug"]
    return table


REGION_LOOKUP = region_lookup()


def normalize_placement(values, fn):
    out = []
    for v in as_list(values):
        slug = REGION_LOOKUP.get(str(v).strip().lower())
        if slug:
            if slug not in out:
                out.append(slug)
        else:
            print(f"  WARNING: content/listings/{fn}: unrecognised state {v!r} -- ignored")
    return out


def clean_listing(a):
    a["businessName"] = (a.get("businessName") or "").strip()
    if not a["businessName"]:
        print(f"  WARNING: skipped content/listings/{a.get('_file')} (no business name)")
        return None
    a["tier"] = normalize_tier(a.get("tier"), a.get("_file"))
    a["placement"] = normalize_placement(a.get("placement"), a.get("_file"))
    a["services"] = as_list(a.get("services"))
    a["badges"] = [str(b).strip() for b in as_list(a.get("badges"))
                   if str(b).strip() and not str(b).startswith(("unlisted_code", "undefined"))]
    a["highlight"] = bool(a.get("highlight"))
    a["pinned"] = bool(a.get("pinned"))
    for k in ("city", "phone", "phone2", "description"):
        a[k] = (a.get(k) or "").strip()
    a["website"] = clean_url(a.get("website"))
    img = (a.get("image") or "").strip()
    if "placeholder" in os.path.basename(img).lower():
        img = ""                      # stock placeholder art is never shown to visitors
    a["image"] = img.lstrip("/")      # page code adds the right "../" prefix
    try:
        a["priority"] = int(a.get("priority") or 100)
    except (TypeError, ValueError):
        a["priority"] = 100
    return a


def clean_hotel(h):
    h["name"] = (h.get("name") or "").strip()
    if not h["name"] or not h.get("state"):
        print(f"  WARNING: skipped content/hotels/{h.get('_file')} (needs a name and a state)")
        return None
    h["notes"] = as_list(h.get("notes"))
    h["website"] = clean_url(h.get("website"))
    return h
with open(os.path.join(DATA, "adjacency.json")) as f:
    ADJACENCY = json.load(f)


def is_live(ad, today=None):
    """An ad shows only if it is switched on and inside its date window.

    Missing dates mean "no limit", so existing ads keep working. When an
    advertiser cancels, setting endDate makes the ad drop off by itself on
    that day -- nobody has to remember to delete it.
    """
    today = today or date.today().isoformat()
    if ad.get("active") is False:
        return False
    if ad.get("startDate") and ad["startDate"] > today:
        return False
    if ad.get("endDate") and ad["endDate"] < today:
        return False
    return True



# Revenue order. Index 0 is most prominent. A higher-paying tier ALWAYS
# outranks a lower one; "priority" only orders ads within the same tier,
# so a mistyped number can never push a basic listing above a banner.
TIER_ORDER = ["global_banner", "state_banner", "super_listing",
              "bold_listing", "basic_listing"]


def ad_sort_key(a):
    tier = a.get("tier", "basic_listing")
    rank = TIER_ORDER.index(tier) if tier in TIER_ORDER else len(TIER_ORDER)
    return (rank, a.get("priority", 999), a.get("businessName", "").lower())


ALL_ADS = [a for a in (clean_listing(x) for x in load_folder("listings")) if a]
ADS = [a for a in ALL_ADS if is_live(a)]


# ---------------------------------------------------------------- ads & lineups
# Ads live in content/ads (one file per ad: artwork, text, contact, dates).
# WHERE each ad shows, and in what ORDER, is decided by lineups:
#   content/nationwide.json         -> Nationwide Sponsors, every page
#   content/lineups/<state>.json    -> that state's State listings and
#                                      Super listings, each its own order
# The same ad can sit in any number of lineups, at a different position in
# each. An ad that is switched off or past its end date drops out everywhere.
def clean_ad(a):
    a["businessName"] = (a.get("businessName") or a.get("name") or "").strip()
    if not a["businessName"]:
        print(f"  WARNING: skipped content/ads/{a.get('_file')} (no advertiser name)")
        return None
    for k in ("phone", "description", "location", "stripColor"):
        a[k] = (a.get(k) or "").strip()
    a["services"] = as_list(a.get("services"))
    a["website"] = clean_url(a.get("website"))
    img = (a.get("image") or "").strip()
    if "placeholder" in os.path.basename(img).lower():
        img = ""
    a["image"] = img.lstrip("/")
    a.setdefault("tier", "super_listing")
    a.setdefault("placement", [])
    return a


AD_LIBRARY = {}
for _a in (clean_ad(x) for x in load_folder("ads")):
    if _a:
        stem = os.path.splitext(_a["_file"])[0]
        for key in (stem, _a["_file"], "content/ads/" + _a["_file"], "/content/ads/" + _a["_file"]):
            AD_LIBRARY[key.lower()] = _a


def resolve_ad(ref, where):
    """A lineup entry -> the ad, or None (missing, switched off, or expired)."""
    if isinstance(ref, dict):
        ref = ref.get("ad")
    key = (str(ref or "")).strip().lower()
    if not key:
        return None
    ad = AD_LIBRARY.get(key) or AD_LIBRARY.get(os.path.splitext(os.path.basename(key))[0])
    if ad is None:
        print(f"  WARNING: {where} lists an ad that doesn't exist: {ref!r}")
        return None
    return ad if is_live(ad) else None


def lineup_entries(items, where):
    """Like lineup_ads, but keeps each entry's own settings (e.g. pinned)."""
    out, seen_ = [], set()
    for it in items or []:
        ad = resolve_ad(it, where)
        if ad is not None and id(ad) not in seen_:
            seen_.add(id(ad)); out.append((ad, it if isinstance(it, dict) else {}))
    return out


def lineup_ads(items, where):
    out, seen_ = [], set()
    for it in items or []:
        ad = resolve_ad(it, where)
        if ad is not None and id(ad) not in seen_:
            seen_.add(id(ad)); out.append(ad)
    return out


def _load_json(rel):
    try:
        with open(os.path.join(CONTENT, rel), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"  WARNING: content/{rel} could not be read ({e})")
        return None


NATIONWIDE = _load_json("nationwide.json")
print(f"Ads: {len({id(a) for a in AD_LIBRARY.values()})} in the Ads section")
LINEUPS = {}
for _doc in load_folder("lineups"):
    if _doc.get("state"):
        LINEUPS[_doc["state"]] = _doc
_counts = {t_: sum(1 for a in ADS if a["tier"] == t_) for t_ in TIER_ORDER}
print("Listings on the site: " + ", ".join(f"{n} {t_.replace('_', ' ')}" for t_, n in _counts.items())
      + f", {sum(1 for a in ADS if a['pinned'])} pinned"
      + f"  ({len(ALL_ADS) - len(ADS)} hidden by date or switched off)")

HOTELS = {}
for _h in (clean_hotel(x) for x in load_folder("hotels")):
    if _h:
        HOTELS.setdefault(_h["state"], {"listings": []})["listings"].append(_h)
with open(os.path.join(DATA, "regulations.json")) as f:
    REGS = json.load(f)["states"]

# Regulations edited in Pages CMS (one file per state) take priority over the
# older hand-written data/regulations.json entries.
REG_PAGES = {}
for _doc in load_folder("regulations"):
    _slug = (_doc.get("region") or "").strip()
    if _slug:
        REG_PAGES[_slug] = _doc


def has_regs(slug):
    return slug in REG_PAGES or slug in REGS


SERVICES_DEFAULTS = {
    "enabled": True,
    "navLabel": "Website & Ad Design",
    "headline": "Need a website or an ad that works?",
    "intro": "We design websites, advertisements, and logos for pilot car companies, hotels, and trucking businesses. Tell us what you need and we'll get back to you with ideas and a price.",
    "relationshipNotice": "Design services are a separate, paid service. They are not included with directory listings or advertising packages.",
    "services": [
        {"title": "Website design", "description": "A clean, mobile-friendly website for your company."},
        {"title": "Advertisement design", "description": "Banner and listing artwork sized for this directory."},
        {"title": "Logo design", "description": "A simple, professional logo you can use everywhere."},
    ],
    "inquiryEmail": "your-email@example.com",
    "formAlias": "",
}


def load_services():
    path = os.path.join(CONTENT, "services.json")
    data = dict(SERVICES_DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            data.update({k: v for k, v in json.load(f).items() if v not in (None, "")})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"  WARNING: content/services.json could not be read ({e}) -- using defaults")
    return data


SERVICES = load_services()
with open(os.path.join(DATA, "truck_stops.json")) as f:
    TRUCKSTOPS = json.load(f)

US_STATES = STATES["us_states"]
CA_PROVINCES = STATES["ca_provinces"]
ALL_REGIONS = US_STATES + CA_PROVINCES
SLUG_TO_NAME = {r["slug"]: r["name"] for r in ALL_REGIONS}

SERVICE_LABELS = {
    "height_pole": "Height pole",
    "route_survey": "Route survey",
    "multi_car": "Multi-car",
    "steering": "Steering",
}

TIER_CLASS = {
    "global_banner": "ad--banner",
    "state_banner": "ad--banner",
    "super_listing": "ad--super",
    "bold_listing": "ad--bold",
    "basic_listing": "ad--basic",
}
TIER_LABEL = {
    "global_banner": "Sitewide Banner",
    "state_banner": "Featured — State Banner",
    "super_listing": "Super Listing",
    "bold_listing": "Bold Listing",
    "basic_listing": "Basic Listing",
}

STATE_CODES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV", "new-hampshire": "NH", "new-jersey": "NJ",
    "new-mexico": "NM", "new-york": "NY", "north-carolina": "NC", "north-dakota": "ND", "ohio": "OH",
    "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode-island": "RI",
    "south-carolina": "SC", "south-dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west-virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

NAV_ITEMS = [
    ("home", "Home", ""),
    ("directory", "Pilot Car Directory", "directory/"),
    ("regulations", "Pilot Car Regulations", "regulations/"),
    ("resources", "Resources", "resources/"),
    ("advertise", "Advertise With Us", "advertise/"),
    ("privacy", "Privacy & Security", "privacy.html"),
]
if SERVICES.get("enabled", True):
    NAV_ITEMS.append(("services", SERVICES.get("navLabel") or "Website & Ad Design", "design-services.html"))


def esc(s):
    return html.escape(s, quote=True) if isinstance(s, str) else s


def region_slugify_check(slug):
    assert re.match(r"^[a-z-]+$", slug), slug


# ---------------------------------------------------------------- fragments
def load_logo():
    """The logo is drawn inline (not as an <img>) so hovering can recolour it.
    It lives in ONE file: assets/images/branding/logo-wordmark.svg."""
    path = os.path.join(ROOT, "assets", "images", "branding", "logo-wordmark.svg")
    try:
        svg = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return f'<span class="brand-text">{esc(SITE_NAME)}</span>'
    svg = re.sub(r"<\?xml[^>]*\?>", "", svg)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)      # keep pages lean
    return svg.strip()


LOGO_SVG = load_logo()


def sidebar_html(base, active_key, active_region_slug=None):
    nav_html_parts = []
    for key, label, href in NAV_ITEMS:
        is_active = "is-active" if key == active_key else ""
        if key == "home":
            full_href = base + "index.html" if base else "index.html"
        elif href.endswith("/"):
            full_href = base + href + "index.html"
        else:
            full_href = base + href
        nav_html_parts.append(
            f'<a class="nav-link {is_active}" href="{full_href}">'
            f'<span class="chevron">&raquo;</span>{esc(label)}</a>'
        )
    nav_block = "\n".join(nav_html_parts)

    # US state placard grid (links into directory section, since that's the
    # primary "find a company" workflow; regulations pages cross-link too)
    placards = []
    for r in US_STATES:
        active = "is-active" if r["slug"] == active_region_slug else ""
        href = f'{base}directory/{r["slug"]}.html'
        code = STATE_CODES.get(r["slug"], r["name"][:2].upper())
        placards.append(
            f'<a class="placard {active}" href="{href}" title="{esc(r["name"])} pilot car directory">{esc(code)}</a>'
        )
    placard_block = "\n".join(placards)

    ca_links = []
    for r in CA_PROVINCES:
        active = "is-active" if r["slug"] == active_region_slug else ""
        href = f'{base}directory/{r["slug"]}.html'
        ca_links.append(f'<a class="nav-link {active}" style="padding-left:28px;font-size:.86rem" href="{href}">{esc(r["name"])}</a>')
    ca_block = "\n".join(ca_links)

    return f"""
    <aside class="sidebar" id="primary-sidebar">
      <div class="sidebar-brand">
        <a class="logo-link" href="{base}index.html" aria-label="{SITE_NAME} home">
          {LOGO_SVG}
        </a>
        <span class="brand-tagline">{SITE_TAGLINE}</span>
      </div>
      <div class="sidebar-scroll">
        <nav class="nav-section" aria-label="Primary">
          {nav_block}
        </nav>
        <div class="nav-section-label">US Pilot Car Directory — Jump to a State</div>
        <div class="placard-grid">
          {placard_block}
        </div>
        <div class="nav-section-label">Canada</div>
        {ca_block}
      </div>
      <div class="sidebar-footer">
        <div>&#9742; Toll-free dispatch: <a href="tel:8662592750">866-259-2750</a></div>
        <div style="margin-top:6px;">&copy; US Pilot Cars LLC — All rights reserved</div>
      </div>
    </aside>
    <div class="scrim" data-scrim></div>
    """


def topbar_html(base):
    return f"""
    <div class="topbar">
      <a class="logo-link" href="{base}index.html" aria-label="{SITE_NAME} home">
        {LOGO_SVG}
      </a>
      <button class="menu-toggle" data-menu-toggle aria-expanded="false" aria-controls="primary-sidebar">&#9776; Menu</button>
    </div>
    """


def ad_card(ad, base, sidebar_style=False):
    tier = ad.get("tier", "basic_listing")
    css_tier = TIER_CLASS.get(tier, "ad--basic")
    label = TIER_LABEL.get(tier, "Listing")
    img_html = ""
    if ad.get("image"):
        img_html = f'<img class="ad-image" src="{base}{ad["image"]}" alt="{esc(ad["businessName"])} advertisement creative" loading="lazy">'
    services = ad.get("services") or []
    chips = "".join(f'<span class="svc-chip">{esc(SERVICE_LABELS.get(s, s))}</span>' for s in services)
    location_bits = []
    if ad.get("city"):
        location_bits.append(ad["city"])
    loc = ", ".join(location_bits)
    actions = []
    if ad.get("phone"):
        phone_digits = re.sub(r"[^\d+]", "", ad["phone"])
        actions.append(f'<a class="btn btn-call btn-sm" href="tel:{phone_digits}">&#9742; {esc(ad["phone"])}</a>')
    if ad.get("phone2"):
        phone_digits2 = re.sub(r"[^\d+]", "", ad["phone2"])
        actions.append(f'<a class="btn btn-outline btn-sm" href="tel:{phone_digits2}">&#9742; {esc(ad["phone2"])}</a>')
    if ad.get("website"):
        actions.append(f'<a class="btn btn-outline btn-sm" href="{esc(ad["website"])}" target="_blank" rel="nofollow noopener">Visit Website &#8599;</a>')
    actions_html = "".join(actions)
    desc_html = f'<p class="ad-desc">{esc(ad["description"])}</p>' if ad.get("description") else ""
    return f"""
    <article class="ad {css_tier}">
      <div class="ad-kicker">{esc(label)}</div>
      {img_html}
      <div class="ad-body">
        <h3 class="ad-name">{esc(ad["businessName"])}</h3>
        <div class="ad-location">{esc(loc)}</div>
        {desc_html}
        <div class="ad-services">{chips}</div>
        <div class="ad-actions">{actions_html}</div>
      </div>
    </article>
    """


# ---------------------------------------------------------------- old-site ads
# Ads imported from the old site keep their original design in "legacyBox":
# a background (colour or picture) plus pieces laid out exactly as before,
# with real text in its original fonts and colours.

_LEGACY_STYLE_OK = {"color", "font-weight", "font-style", "text-decoration", "font-family",
                    "line-height", "background-color", "text-align", "--fs"}
_PHONE_RE = re.compile(r"\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b")


class _LegacySanitizer(HTMLParser):
    """Like the regulations sanitizer, but keeps the safe text styling the
    old ads depend on, and makes phone numbers tap-to-call."""
    ALLOWED = {"p", "br", "span", "a", "b", "strong", "i", "em", "u"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.in_a, self.skip = [], 0, 0

    def _style(self, raw):
        keep = []
        for decl in (raw or "").split(";"):
            if ":" not in decl:
                continue
            k, v = (x.strip() for x in decl.split(":", 1))
            if k.lower() in _LEGACY_STYLE_OK and re.fullmatch(r"[#\w\s.,'\"%()-]+", v) and "url" not in v.lower() and "expression" not in v.lower():
                keep.append(f"{k}:{v}")
        return ";".join(keep)

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object", "embed", "form"):
            self.skip += 1; return
        if self.skip or tag not in self.ALLOWED:
            return
        a = dict(attrs)
        if tag == "br":
            self.out.append("<br>"); return
        st = self._style(a.get("style"))
        st_attr = f' style="{esc(st)}"' if st else ""
        if tag == "a":
            href = a.get("href", "") or ""
            if re.match(r"^(https?://|mailto:|tel:)", href, re.I):
                ext = ' target="_blank" rel="nofollow noopener"' if href.lower().startswith("http") else ""
                self.out.append(f'<a href="{esc(href)}"{ext}{st_attr}>')
            else:
                self.out.append(f"<a{st_attr}>")
            self.in_a += 1
        else:
            self.out.append(f"<{tag}{st_attr}>")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object", "embed", "form"):
            self.skip = max(0, self.skip - 1); return
        if not self.skip and tag in self.ALLOWED and tag != "br":
            if tag == "a":
                self.in_a = max(0, self.in_a - 1)
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if self.skip:
            return
        if self.in_a:
            self.out.append(esc(data)); return
        last = 0
        for m in _PHONE_RE.finditer(data):
            self.out.append(esc(data[last:m.start()]))
            self.out.append(f'<a class="lb-tel" href="{tel_href(m.group(0))}">{esc(m.group(0))}</a>')
            last = m.end()
        self.out.append(esc(data[last:]))


def sanitize_legacy(raw):
    s = _LegacySanitizer(); s.feed(raw or ""); s.close()
    return "".join(s.out)


def legacy_ad(ad, base):
    box = ad.get("legacyBox") or {}
    label = esc(ad["businessName"])
    if box.get("flow"):
        return (f'<div class="lbox-wrap lbox-wrap-flow"><div class="lbox lbox-flow" role="group" aria-label="{label}">'
                f'{sanitize_legacy(box.get("html"))}</div></div>')
    W, H = max(1, int(box.get("w") or 1)), max(1, int(box.get("h") or 1))
    bg_color, bg_img, pieces = "", "", []
    for p in box.get("parts") or []:
        x, y, w, h = (float(p.get(k) or 0) for k in ("x", "y", "w", "h"))
        covers = w * h >= 0.8 * W * H
        if p.get("type") == "fill" and covers and not bg_color:
            bg_color = p.get("color", ""); continue
        if p.get("type") == "img" and covers and not bg_img:
            bg_img = p.get("src", ""); continue
        if p.get("type") == "text" and covers and p.get("color") and not bg_color:
            bg_color = p["color"]; p = dict(p, color="")      # coloured panel fills the whole box
        geo = f"left:{x / W * 100:.2f}%;top:{y / H * 100:.2f}%;width:{w / W * 100:.2f}%;height:{h / H * 100:.2f}%"
        if p.get("type") == "fill":
            pieces.append(f'<div class="lp lp-fill" style="{geo};background:{esc(p.get("color", ""))}"></div>')
        elif p.get("type") == "img":
            pieces.append(f'<img class="lp lp-img" src="{base}{esc(p.get("src", "").lstrip("/"))}" alt="" loading="lazy" style="{geo}">')
        elif p.get("type") == "text":
            fill = f";background:{esc(p['color'])}" if p.get("color") else ""
            pieces.append(f'<div class="lp lp-text" style="{geo}{fill}">{sanitize_legacy(p.get("html"))}</div>')
    bg = []
    if bg_color and re.fullmatch(r"#[0-9a-fA-F]{6}", bg_color):
        bg.append(f"background-color:{bg_color}")
    if bg_img:
        bg.append(f"background-image:url('{base}{esc(bg_img.lstrip('/'))}')")
    style = f"--w:{W};aspect-ratio:{W} / {H};" + ";".join(bg)
    return (f'<div class="lbox-wrap"><div class="lbox" style="{style}" role="group" aria-label="{label}">'
            f'{"".join(pieces)}</div></div>')


def banner_ad(ad, base):
    """A paid banner, shown the way the old site showed it: the advertiser's
    own artwork, full width, clickable. If there's no artwork yet, a clean
    text version so the advertiser still gets their space."""
    if ad.get("legacyBox"):
        return legacy_ad(ad, base)
    name = esc(ad["businessName"])
    href = ad.get("website") or ""
    if ad.get("image"):
        inner = f'<img src="{base}{esc(ad["image"])}" alt="{name} advertisement" loading="lazy" decoding="async">'
    else:
        bits = [f'<span class="bf-name">{name}</span>']
        if ad.get("description"):
            bits.append(f'<span class="bf-desc">{esc(ad["description"])}</span>')
        if ad.get("phone"):
            bits.append(f'<span class="bf-phone">&#9742; {esc(ad["phone"])}</span>')
        inner = f'<span class="banner-fallback">{"".join(bits)}</span>'
    if href:
        return f'<a class="banner-ad" href="{esc(href)}" target="_blank" rel="sponsored noopener">{inner}</a>'
    return f'<div class="banner-ad">{inner}</div>'


def sitewide_banners():
    """Nationwide Sponsors, in the order set in the editor. (Falls back to
    the older 'Sitewide banner' package if no nationwide list exists yet.)"""
    if NATIONWIDE is not None:
        return lineup_ads(NATIONWIDE.get("sponsors"), "Nationwide Sponsors")
    return sorted([a for a in ADS if a["tier"] == "global_banner"], key=ad_sort_key)


SPONSOR_SECTION_TITLE = "Nationwide Sponsors"
SPONSOR_SECTION_NOTE = "Featured on every page across the US &amp; Canada"


def page_section(key, title, note, inner, count=None, extra_class=""):
    """One collapsible section of a state page. Starts open; a visitor can
    fold it away. Built on <details>, so it works without JavaScript and
    with keyboards and screen readers."""
    n = f'<span class="sec-count">{count}</span>' if count is not None else ""
    return f"""<details class="page-section sec-{key} {extra_class}" open>
      <summary class="sponsor-band-head">
        <h2>{title} {n}</h2><span class="sb-note">{note}</span><span class="sec-toggle" aria-hidden="true"></span>
      </summary>
      <div class="sec-body">{inner}</div>
    </details>"""


def sitewide_banner_block(base):
    """Section 3: Nationwide Sponsors -- under the title on every page."""
    ads = sitewide_banners()
    if not ads:
        return ""
    return page_section("national", "&#9733; " + SPONSOR_SECTION_TITLE, SPONSOR_SECTION_NOTE,
                        f'<div class="banner-row">{"".join(banner_ad(a, base) for a in ads)}</div>',
                        extra_class="sponsor-band")


# ---------------------------------------------------------------- strip builder
# State listings designed right in the editor. Every option below comes from
# a survey of the 66 coloured strip ads on the old site: their backgrounds,
# text colours, fonts and sizes.
PALETTE = {
    "black": "#000000", "white": "#ffffff", "light-gray": "#ebebeb", "gray": "#808080",
    "red": "#ff0000", "dark-red": "#a80000", "pink": "#ff6b6b", "light-pink": "#fff5ff",
    "orange": "#ff8000", "yellow": "#ffff00", "gold": "#e6b800",
    "bright-green": "#00ff00", "green": "#07b300", "dark-green": "#006400", "olive": "#adca56",
    "aqua": "#00ffff", "teal": "#008080", "blue": "#0000ff", "navy": "#000080", "purple": "#800080",
    "brown": "#553f1f",
}
FONTS = {
    "tahoma": "Tahoma, Verdana, 'Segoe UI', Arial, sans-serif",
    "verdana": "Verdana, Tahoma, Arial, sans-serif",
    "arial": "Arial, Helvetica, sans-serif",
    "arial-black": "'Arial Black', 'Arial Bold', Gadget, Arial, sans-serif",
    "rockwell": "'Rockwell Extra Bold', Rockwell, 'Roboto Slab', Georgia, 'Times New Roman', serif",
    "georgia": "Georgia, 'Times New Roman', serif",
    "times": "'Times New Roman', Times, Georgia, serif",
    "impact": "Impact, 'Arial Narrow Bold', 'Arial Black', sans-serif",
}
SIZES = {"small": 9, "normal": 11, "medium": 13, "large": 15, "x-large": 19, "huge": 24}   # old-site px
DIRECTIONS = {"right": "to right", "down": "to bottom", "diagonal": "135deg"}
# Older ads saved before the builder existed: one plain strip colour.
STRIP_COLORS = {"blue": "blue", "red": "red", "aqua": "aqua", "yellow": "yellow", "green": "bright-green",
                "navy": "navy", "white": "white"}


def _col(name, default):
    return PALETTE.get((name or "").strip().lower(), PALETTE.get(default, default))


def _ink_for(bg_hex):
    r, g, b = (int(bg_hex[i:i + 2], 16) for i in (1, 3, 5))
    return "#000000" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


def strip_background(st, base):
    kind = (st.get("background") or "solid").lower()
    c1 = _col(st.get("color1"), "white")
    if kind == "gradient":
        stops = [c1] + ([_col(st["color2"], "white")] if st.get("color2") else []) + \
                ([_col(st["color3"], "white")] if st.get("color3") else [])
        if len(stops) == 1:
            stops.append(c1)
        d = (st.get("direction") or "right").lower()
        if d == "shine":
            return f"background:radial-gradient(ellipse at center, {', '.join(reversed(stops))})", c1
        return f"background:linear-gradient({DIRECTIONS.get(d, 'to right')}, {', '.join(stops)})", c1
    if kind == "picture" and st.get("backgroundImage"):
        img = esc(st["backgroundImage"].lstrip("/"))
        return f"background:{c1} url('{base}{img}') center / 100% 100% no-repeat", c1
    return f"background:{c1}", c1


def strip_line_html(text, ad, st, ink):
    """One line of a designed strip. Coloured automatically, the way the old
    strips were: the company name (linked to their website, optionally a size
    bigger), phone numbers (tap-to-call), and any extra words picked out in
    their own colour (e.g. "Bucket Trucks" in teal)."""
    name = ad["businessName"]
    name_c = _col(st.get("nameColor"), ink) if st.get("nameColor") else None
    phone_c = _col(st.get("phoneColor"), ink) if st.get("phoneColor") else None
    extra = {}
    for h in st.get("highlights") or []:
        w = (h.get("text") or "").strip()
        if w:
            extra[w.lower()] = _col(h.get("color"), ink)
    alts = []
    if name:
        alts.append("(?P<name>" + re.escape(name) + ")")
    if extra:
        alts.append("(?P<extra>" + "|".join(re.escape(w) for w in sorted(extra, key=len, reverse=True)) + ")")
    alts.append(r"(?P<phone>\(?\b\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b)")
    pattern = re.compile("|".join(alts), re.I)
    out, last = [], 0
    for m in pattern.finditer(text):
        out.append(esc(text[last:m.start()]))
        seg = m.group(0)
        if m.lastgroup == "name":
            css = []
            if name_c:
                css.append(f"color:{name_c}")
            if st.get("nameBigger"):
                css.append("font-size:1.25em")
            style = f' style="{";".join(css)}"' if css else ""
            out.append(f'<a class="sl-name" href="{esc(ad["website"])}" target="_blank" rel="sponsored noopener"{style}>{esc(seg)}</a>'
                       if ad.get("website") else f'<span class="sl-name"{style}>{esc(seg)}</span>')
        elif m.lastgroup == "extra":
            out.append(f'<span style="color:{extra[seg.lower()]}">{esc(seg)}</span>')
        else:
            style = f' style="color:{phone_c}"' if phone_c else ""
            out.append(f'<a class="sl-phone" href="{tel_href(seg)}"{style}>{esc(seg)}</a>')
        last = m.end()
    out.append(esc(text[last:]))
    return "".join(out)


def built_strip(ad, base):
    st = ad.get("strip") or {}
    bg_css, c1 = strip_background(st, base)
    ink = _col(st.get("textColor"), _ink_for(c1))
    font = FONTS.get((st.get("font") or "tahoma").lower(), FONTS["tahoma"])
    border = (st.get("border") or "none").lower()
    bw = {"thin": 2, "thick": 4}.get(border, 0)
    border_css = (f";border:{bw}px {'dashed' if (st.get('borderStyle') or '').lower() == 'dashed' else 'solid'} "
                  f"{_col(st.get('borderColor'), 'black')}") if bw else ";border:1px solid rgba(0,0,0,.15)"
    align = "left" if (st.get("align") or "").lower() == "left" else "center"
    lines = []
    for ln in st.get("lines") or []:
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        px = SIZES.get((ln.get("size") or "normal").lower(), 11)
        css = [f"--fs:{px}"]
        css.append("font-weight:700" if ln.get("bold", True) is not False else "font-weight:400")
        if ln.get("italic"):
            css.append("font-style:italic")
        if ln.get("underline"):
            css.append("text-decoration:underline")
        if ln.get("color"):
            css.append(f"color:{_col(ln['color'], ink)}")
        if ln.get("font") and ln["font"].lower() in FONTS:
            css.append(f"font-family:{FONTS[ln['font'].lower()]}")
        lines.append(f'<div class="sl-line" style="{";".join(css)}">{strip_line_html(text, ad, st, ink)}</div>')
    logo = (f'<img class="sl-logo" src="{base}{esc(st["logo"].lstrip("/"))}" alt="" loading="lazy">'
            if st.get("logo") else "")
    return (f'<div class="ad-strip ad-strip-built" style="{bg_css}{border_css};color:{ink};font-family:{font};text-align:{align}">'
            f'{logo}<div class="sl-lines">{"".join(lines)}</div></div>')


def auto_strip(ad):
    """No design yet: make one from the ad's own details, so a new ad shows
    sensibly the moment it is added."""
    loc = f'{ad["location"]} | ' if ad.get("location") else ""
    lines = [{"text": f'{loc}{ad["businessName"]}{" | " + ad["phone"] if ad.get("phone") else ""}', "size": "medium"}]
    if ad.get("description"):
        lines.append({"text": ad["description"], "size": "normal"})
    color = STRIP_COLORS.get((ad.get("stripColor") or "white").lower(), "white")
    return {"background": "solid", "color1": color, "nameColor": "", "phoneColor": "red" if color in ("white", "yellow", "aqua", "bright-green", "light-gray") else "",
            "lines": lines}


def compact_ad(ad, base):
    """Section 4, a State listing: a half-height strip. Designed in the editor
    (strip builder), or a picture, or -- for a brand-new ad -- made
    automatically from its details."""
    if ad.get("legacyBox"):
        return f'<div class="ad-strip ad-strip-legacy">{legacy_ad(ad, base)}</div>'
    st = ad.get("strip") or {}
    if any((l or {}).get("text") for l in st.get("lines") or []):
        return built_strip(ad, base)
    if ad.get("image"):
        name = esc(ad["businessName"]); href = ad.get("website") or ""
        img = f'<img src="{base}{esc(ad["image"])}" alt="{name} advertisement" loading="lazy" decoding="async">'
        return (f'<a class="ad-strip ad-strip-img" href="{esc(href)}" target="_blank" rel="sponsored noopener">{img}</a>'
                if href else f'<div class="ad-strip ad-strip-img">{img}</div>')
    return built_strip(dict(ad, strip=auto_strip(ad)), base)


def super_ad(ad, base, pinned=False):
    """Section 5, a Super listing: a short text ad in the two-column block --
    company name (with services), city, phone in red -- as on the old site."""
    if ad.get("legacyBox"):
        return f'<div class="super-entry">{legacy_ad(ad, base)}</div>'
    name = esc(ad["businessName"])
    href = ad.get("website") or ""
    title = f'<a href="{esc(href)}" target="_blank" rel="sponsored noopener">{name}</a>' if href else name
    svcs = "".join(f'<span class="se-svc">{esc(SERVICE_LABELS[s])}</span>' for s in ad.get("services") or [] if s in SERVICE_LABELS)
    img = (f'<img class="se-img" src="{base}{esc(ad["image"])}" alt="{name} advertisement" loading="lazy">'
           if ad.get("image") else "")
    parts = ['<div class="pin-tag">&#9733; Top listing</div>'] if pinned else []
    parts.append(f'<div class="se-name">{title}</div>')
    if svcs:
        parts.append(f'<div class="se-svcs">{svcs}</div>')
    if img:
        parts.append(img)
    if ad.get("location"):
        parts.append(f'<div class="se-loc">{esc(ad["location"])}</div>')
    if ad.get("description"):
        parts.append(f'<div class="se-desc">{esc(ad["description"])}</div>')
    if ad.get("phone"):
        parts.append(f'<a class="se-phone" href="{tel_href(ad["phone"])}">{esc(ad["phone"])}</a>')
    return f'<div class="super-entry{" super-pinned" if pinned else ""}">{"".join(parts)}</div>'


# Section 5 uses two columns only when there are enough listings to fill
# them (Oregon's 14 -> two columns; Wyoming's 4 -> one), as on the old site.
SUPER_TWO_COLUMN_MIN = 6


def state_sections(slug, state_name, base):
    """Sections 4 and 5 for one state, from that state's lineup.
    Section 4 is titled "State Listings" on every page (not the state's name):
    companies from anywhere can advertise on any state's page."""
    lu = LINEUPS.get(slug) or {}
    state_listings = lineup_ads(lu.get("stateListings"), f"{state_name} State listings")
    supers = lineup_entries(lu.get("superListings"), f"{state_name} Super listings")
    # Paid "pin to top": pinned Super listings come first, in their list order.
    pinned = [a for a, it in supers if it.get("pinned")]
    rest = [a for a, it in supers if not it.get("pinned")]
    html_ = ""
    if state_listings:
        html_ += page_section("state", "&#9670; State Listings", f"Pilot car companies serving {esc(state_name)}",
                              f'<div class="strip-grid">{"".join(compact_ad(a, base) for a in state_listings)}</div>',
                              count=len(state_listings), extra_class="sponsor-band in-content")
    if supers:
        inner = ""
        if pinned:
            inner += f'<div class="super-pinned-row">{"".join(super_ad(a, base, pinned=True) for a in pinned)}</div>'
        if rest:
            one = " super-list-one" if len(rest) < SUPER_TWO_COLUMN_MIN else ""
            inner += f'<div class="super-list{one}">{"".join(super_ad(a, base) for a in rest)}</div>'
        html_ += page_section("super", "Super Listings", f"Featured companies serving {esc(state_name)}",
                              inner, count=len(supers), extra_class="sponsor-band in-content")
    return html_, state_listings + [a for a, _ in supers]


def place_after_page_banner(body, block):
    """Insert the sponsor section right after the page's title banner
    (the dark 'page-header' on inner pages, the 'hero' on the home page).
    Finds the banner's real closing tag by counting nested tags."""
    if not block:
        return body
    m = re.search(r'<(div|section) class="(?:page-header|hero)"', body)
    if not m:
        return block + body
    tag = m.group(1)
    depth = 0
    for t_ in re.finditer(rf"<(/?){tag}\b[^>]*>", body[m.start():]):
        depth += -1 if t_.group(1) else 1
        if depth == 0:
            end = m.start() + t_.end()
            return body[:end] + block + body[end:]
    return block + body


def sponsor_aside(base):
    """Right-hand column of sitewide text ads (super and bold listings set to
    'Every page'), as on the old site's regulations pages."""
    ads = sorted([a for a in ADS if "sitewide" in a["placement"] and a["tier"] != "global_banner"], key=ad_sort_key)
    if not ads:
        return ""
    return ('<aside class="sponsor-aside" aria-label="Sponsors"><div class="aside-label">Sponsors</div>'
            + "".join(ad_card(a, base) for a in ads) + "</aside>")


def canonical_url(path):
    """Cloudflare Pages serves /directory/texas.html at /directory/texas
    and redirects the .html form there, so canonical addresses (and the
    sitemap) use the clean form. Pointing a canonical at an address that
    redirects would confuse search engines."""
    if path.endswith("index.html"):
        path = path[: -len("index.html")]
    elif path.endswith(".html"):
        path = path[: -len(".html")]
    return f"{SITE_URL}/{path}"


def page_shell(*, base, title, meta_description, active_key, body_html,
               active_region_slug=None, breadcrumbs=None, canonical_path=""):
    crumbs_html = ""
    if breadcrumbs:
        parts = []
        for i, (label, href) in enumerate(breadcrumbs):
            if href:
                parts.append(f'<a href="{base}{href}">{esc(label)}</a>')
            else:
                parts.append(f'<span aria-current="page">{esc(label)}</span>')
        crumbs_html = f'<div class="breadcrumbs">' + '<span class="sep">/</span>'.join(parts) + '</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(meta_description)}">
<link rel="canonical" href="{canonical_url(canonical_path)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta_description)}">
<meta property="og:url" content="{canonical_url(canonical_path)}">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{base}assets/images/branding/logo-mark.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700&family=Source+Sans+3:wght@400;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}assets/css/style.css">
</head>
<body>
<a class="visually-hidden" href="#main-content">Skip to main content</a>
{topbar_html(base)}
<div class="app-shell">
{sidebar_html(base, active_key, active_region_slug)}
<div class="main-col">
  <main id="main-content">
  {crumbs_html and f'<div style="padding:14px 40px 0"><div class="breadcrumbs-wrap">{crumbs_html}</div></div>' or ""}
  {place_after_page_banner(body_html, sitewide_banner_block(base))}
  </main>
  <footer class="site-footer">
    <div><strong>{SITE_NAME} LLC</strong> &trade; — All rights reserved.</div>
    <div class="links">
      <a href="{base}index.html">Home</a>
      <a href="{base}directory/index.html">Find a Pilot Car</a>
      <a href="{base}advertise/index.html">Advertise Your Company</a>
      <a href="{base}regulations/index.html">Pilot Car Regulations</a>
      <a href="{base}privacy.html">Privacy</a>
    </div>
  </footer>
</div>
</div>
<script src="{base}assets/js/main.js"></script>
</body>
</html>
"""


def write(path, contents, *, into=None):
    full = os.path.join(into or OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(contents)


# ---------------------------------------------------------------- HOME
def build_home():
    base = ""
    body = f"""
    <section class="hero">
      <div class="eyebrow">Est. serving the oversize-load industry</div>
      <h1>Find a Pilot Car. Fast.</h1>
      <p class="lead">The pilot car, escort vehicle, and flag car directory truckers, dispatchers, and permit offices already know — now easier to scan, faster on a phone, and just as fast to call.</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="directory/index.html">Find A Pilot Car &rarr;</a>
        <a class="btn btn-outline" style="color:#fff;border-color:#fff" href="advertise/index.html">Advertise Your Company</a>
      </div>
    </section>
    <div class="stat-strip">
      <div class="stat"><div class="num">50</div><div class="label">US States Covered</div></div>
      <div class="stat"><div class="num">11</div><div class="label">Canadian Provinces</div></div>
      <div class="stat"><div class="num">24/7</div><div class="label">Directory Access</div></div>
      <div class="stat"><div class="num">866-259-2750</div><div class="label">Toll-Free Dispatch</div></div>
    </div>
    <div class="content">
      <div class="two-col">
        <div>
          <div class="panel">
            <h2>Extensive Pilot Car Directory</h2>
            <p>Pilot cars are essential for the safety of your truck driver, their cargo, and other drivers on the road while transporting larger-than-normal loads. Wherever you need a pilot driver, our directory helps you find qualified, licensed drivers and dispatchers who can get your cargo to its destination safely and on time.</p>
            <p>Alongside contact information for pilot, escort, and flag car providers, we offer everything companies need to plan an oversize move: <a href="resources/road-conditions.html">road conditions</a>, <a href="resources/hotels.html">hotel lists</a>, permitting and insurance resources, and <a href="regulations/index.html">state and province guidelines</a>.</p>
            <a class="btn btn-primary" href="directory/index.html">Browse the Directory</a>
          </div>
          <div class="panel">
            <h2>Links to Drivers in Every US State and Canadian Province</h2>
            <p>When you're transporting oversize machinery across state or provincial lines, an escort service that knows local roads, curfews, and permit rules keeps your driver, your cargo, and the public safe. We list pilot car operators for every US state (except Hawaii, where the legacy directory did not maintain listings) and 11 Canadian provinces and territories.</p>
            <div class="region-grid" style="margin-top:12px">
              <a class="region-tile" href="directory/new-mexico.html"><span>New Mexico</span><span class="code">NM</span></a>
              <a class="region-tile" href="directory/texas.html"><span>Texas</span><span class="code">TX</span></a>
              <a class="region-tile" href="directory/california.html"><span>California</span><span class="code">CA</span></a>
              <a class="region-tile" href="directory/index.html"><span>All States &rarr;</span></a>
            </div>
          </div>
          <div class="feature-grid">
            <div class="feature-card">
              <div class="icon">&#9873;</div>
              <h3>Pilot Car Regulations</h3>
              <p>State-by-state escort, equipment, and permit requirements, sourced from official guidelines.</p>
              <a href="regulations/index.html">View Regulations &rarr;</a>
            </div>
            <div class="feature-card">
              <div class="icon">&#127976;</div>
              <h3>Hotel List</h3>
              <p>Discounted, pilot-car-friendly hotels near common oversize routes.</p>
              <a href="resources/hotels.html">Find A Hotel &rarr;</a>
            </div>
            <div class="feature-card">
              <div class="icon">&#128666;</div>
              <h3>Truck Stop List</h3>
              <p>Truck stop and fuel stop locations by state for overnight parking.</p>
              <a href="resources/truck-stops.html">View Truck Stops &rarr;</a>
            </div>
          </div>
        </div>
        <aside class="ad-sidebar-stack">
          {"".join(ad_card(a, base) for a in ads_for_placement("sitewide") if a["tier"] != "global_banner")}
          <div class="panel" style="text-align:center">
            <h3>Advertise Here</h3>
            <p>Multi-state, super listings, and specialty ads for your highly targeted audience.</p>
            <a class="btn btn-primary btn-sm" href="advertise/index.html">See Options</a>
          </div>
        </aside>
      </div>
    </div>
    """
    html_out = page_shell(base=base, title=f"{SITE_NAME} | Pilot Car, Escort Car & Flag Car Directory",
                           meta_description="Find a pilot car, escort vehicle, or flag car service. Extensive US and Canada pilot car directory, state regulations, hotel and truck stop lists.",
                           active_key="home", body_html=body, canonical_path="index.html")
    write("index.html", html_out)


def ads_for_placement(slug):
    return sorted([a for a in ADS if slug in a.get("placement", [])], key=ad_sort_key)


# ---------------------------------------------------------------- DIRECTORY
def build_directory_hub():
    base = "../"
    def region_grid(regions, prefix=""):
        tiles = []
        for r in regions:
            count = len(ads_for_placement(r["slug"]))
            unavailable = "is-unavailable" if r.get("no_legacy_directory") else ""
            note = " (no legacy listings)" if r.get("no_legacy_directory") else (f" &middot; {count} listed" if count else "")
            tiles.append(
                f'<a class="region-tile {unavailable}" data-filter-text="{esc(r["name"])}" href="{r["slug"]}.html">'
                f'<span>{esc(r["name"])}{note}</span></a>'
            )
        return "".join(tiles)

    body = f"""
    <div class="page-header">
      <div class="eyebrow">Find A Pilot Car</div>
      <h1>Pilot Car Directory</h1>
      <p>Find the right driver with our pilot car directory. We have connections with pilot, escort, and flag car operators throughout the US and Canada. Choose a state or province below.</p>
    </div>
    <div class="content" style="max-width:1180px">
      <div class="search-row">
        <input type="search" placeholder="Search states or provinces&hellip;" aria-label="Search states or provinces" data-filter-input=".region-tile">
      </div>
      <div class="panel">
        <h2>United States</h2>
        <div class="region-grid">{region_grid(US_STATES)}</div>
      </div>
      <div class="panel">
        <h2>Canada</h2>
        <div class="region-grid">{region_grid(CA_PROVINCES)}</div>
      </div>
      <div class="callout">
        Own a pilot car company and don't see full details for your state yet? <a href="../advertise/index.html">See advertising options</a> or email
        <a href="mailto:support@uspc-llc.com">support@uspc-llc.com</a> to get listed.
      </div>
    </div>
    """
    html_out = page_shell(base=base, title=f"Pilot Car Directory | {SITE_NAME}",
                           meta_description="Browse the pilot car and escort vehicle directory by US state or Canadian province.",
                           active_key="directory", body_html=body, canonical_path="directory/index.html",
                           breadcrumbs=[("Home", "index.html"), ("Pilot Car Directory", None)])
    write("directory/index.html", html_out)


def tel_href(phone):
    return "tel:" + re.sub(r"[^0-9+]", "", phone or "")


def service_chips(services):
    return "".join(f'<span class="svc-chip">{esc(SERVICE_LABELS.get(s, s))}</span>'
                   for s in services or [])


def company_row(a, pinned=False):
    """One pilot car company in the city table. Paid upgrades (bold and
    above) are visibly bolder than basic listings -- that difference is
    what a Bold Listing customer is paying for."""
    tier = a.get("tier", "basic_listing")
    row_class = "row-basic" if tier == "basic_listing" else "row-bold"
    if a.get("highlight"):
        row_class += " row-highlight"
    if pinned:
        row_class += " row-pinned"
    name = esc(a["businessName"])
    if a.get("website"):
        name = f'<a href="{esc(a["website"])}" target="_blank" rel="nofollow noopener">{name}</a>'
    phones = "".join(
        f'<a href="{tel_href(ph)}">{esc(ph)}</a>'
        for ph in (a.get("phone"), a.get("phone2")) if ph)
    chips = service_chips(a.get("services")) + "".join(
        f'<span class="svc-chip badge-chip">{esc(b)}</span>' for b in a.get("badges") or [])
    tag = f'<div class="co-tag">{esc(a["description"])}</div>' if a.get("description") and tier in ("basic_listing", "bold_listing") else ""
    return f"""<tr class="{row_class}">
      <td class="city">{esc(a.get("city") or "")}</td>
      <td>{'<div class="pin-tag">&#9733; Top listing</div>' if pinned else ''}<div class="co-name">{name}</div>{tag}{f'<div class="co-svcs">{chips}</div>' if chips else ''}</td>
      <td class="phone">{phones}</td>
    </tr>"""


def hotel_row(h):
    """A paid hotel placement, shown INSIDE the city table among the pilot
    car companies for the same city. That adjacency is the product: a
    driver looking up Amarillo pilot cars sees the Amarillo hotel right
    there. (The previous rebuild moved hotels to a separate page, which
    removed exactly what hotel advertisers were paying for.)"""
    notes = " &middot; ".join(esc(n) for n in h.get("notes") or [])
    name = esc(h["name"])
    if h.get("website"):
        name = f'<a href="{esc(h["website"])}" target="_blank" rel="nofollow noopener">{name}</a>'
    phone = f'<a href="{tel_href(h["phone"])}">{esc(h["phone"])}</a>' if h.get("phone") else ""
    return f"""<tr class="row-hotel">
      <td class="city">{esc(h.get("city") or "")}</td>
      <td><div class="hotel-tag">Hotel</div><div class="co-name">{name}</div>
          <div class="hotel-meta">{esc(h.get("address") or "")}{' &middot; ' + notes if notes else ''}</div></td>
      <td class="phone">{phone}</td>
    </tr>"""


def nearby_html(slug, section):
    """Links to neighbouring states/provinces, generated from
    data/adjacency.json -- nobody maintains these by hand."""
    neighbours = [n for n in ADJACENCY.get(slug, []) if n in SLUG_TO_NAME]
    if not neighbours:
        return ""
    links = "".join(
        f'<li><a href="../{section}/{n}.html">{esc(SLUG_TO_NAME[n])}</a></li>'
        for n in sorted(neighbours, key=lambda n: SLUG_TO_NAME[n]))
    label = "pilot car directories" if section == "directory" else "regulations"
    return f"""<nav class="panel nearby" aria-label="Nearby {label}">
      <h2>Nearby {label}</h2><ul>{links}</ul></nav>"""


def build_directory_state_pages():
    for r in ALL_REGIONS:
        base = "../"
        slug = r["slug"]
        name = r["name"]
        region_ads = ads_for_placement(slug)          # already tier-ordered
        hotels = [h for h in HOTELS.get(slug, {}).get("listings", []) if is_live(h)]

        # 1. Banners and super listings: big cards at the TOP of the page.
        # Sitewide banners are already at the top of every page. Here: this
        # state's own paid ads, between that block and the listings table,
        # as on the old site.
        featured_html, _lineup_ads = state_sections(slug, name, base)

        # 2. The city table: every company plus hotels, grouped by city.
        #    Within a city: hotel placement first, then companies by tier.
        # "Pin to top of the state list" (a paid upgrade): those listings come
        # first, above every city, in package-then-order sequence. Everyone
        # else stays grouped by city as on the old site.
        # Banner and super ads already have their own spot above the table.
        # They also appear IN the table only if they list a city -- otherwise
        # a blank-city row would sort to the very top, giving a free "top of
        # the list" spot that pinned customers pay for.
        table_ads = [a for a in region_ads
                     if a["tier"] in ("bold_listing", "basic_listing") or (a.get("city") or "").strip()]
        pinned = [a for a in table_ads if a.get("pinned")]        # region_ads is already in order
        rows = [(a.get("city") or "", 1, ad_sort_key(a), company_row(a)) for a in table_ads if not a.get("pinned")]
        rows += [(h.get("city") or "", 0, (0,), hotel_row(h)) for h in hotels]
        rows.sort(key=lambda x: (x[0].lower(), x[1], x[2]))

        if rows or pinned:
            legend = "".join(f'<span class="svc-chip">{esc(v)}</span>' for v in SERVICE_LABELS.values())
            table_inner = f"""
              <p class="legend">Services offered are shown under each company: {legend}</p>
              <div class="table-scroll">
              <table class="listing-table">
                <thead><tr><th>City</th><th>Company</th><th>Phone</th></tr></thead>
                <tbody>{''.join(company_row(a, pinned=True) for a in pinned)}{''.join(row for *_, row in rows)}</tbody>
              </table>
              </div>"""
            table_html = page_section("basic", f"{esc(name)} Pilot Car Directory", "Every company, by city",
                                      table_inner, count=len(pinned) + sum(1 for r_ in rows if r_[1] == 1),
                                      extra_class="sponsor-band in-content")
        else:
            table_html = f"""
            <div class="panel">
              <h2>No {esc(name)} listings yet</h2>
              <p>We don't have any {esc(name)} pilot car companies listed yet.</p>
              <p>Run a pilot car service in {esc(name)}? <a href="../advertise/index.html">Get listed here</a>,
                 or call <a href="tel:8662592750">866-259-2750</a>.</p>
            </div>"""

        reg_note = ""
        if has_regs(slug):
            reg_note = f'<div class="callout">Planning a move through {esc(name)}? Review the <a href="../regulations/{slug}.html">{esc(name)} pilot car regulations</a> before you dispatch.</div>'

        body = f"""
        <div class="page-header">
          <div class="eyebrow">Pilot Car Directory</div>
          <h1>{esc(name)} Pilot Car Service</h1>
          <p>Find {esc(name)} pilot car, escort car, and flag car companies. Tap a phone number to call.</p>
        </div>
        <div class="content content-wide">
          {featured_html}
          {table_html}
          {reg_note}
          {nearby_html(slug, "directory")}
        </div>
        """
        html_out = page_shell(base=base, title=f"{name} Pilot Car, Pilot Car Service, Pilot Car Directory | {SITE_NAME}",
                               meta_description=f"Find a {name} pilot car service. {name} pilot car directory and listings for escort and flag car companies.",
                               active_key="directory", active_region_slug=slug, body_html=body,
                               canonical_path=f"directory/{slug}.html",
                               breadcrumbs=[("Home", "index.html"), ("Pilot Car Directory", "directory/index.html"), (name, None)])
        write(f"directory/{slug}.html", html_out)


# ---------------------------------------------------------------- REGULATIONS
def build_regulations_hub():
    base = "../"
    def region_grid(regions):
        tiles = []
        for r in regions:
            has = has_regs(r["slug"])
            note = "" if has else " (verify)"
            cls = "" if has else "is-unavailable"
            tiles.append(f'<a class="region-tile {cls}" data-filter-text="{esc(r["name"])}" href="{r["slug"]}.html"><span>{esc(r["name"])}{note}</span></a>')
        return "".join(tiles)

    body = f"""
    <div class="page-header">
      <div class="eyebrow">Rules &amp; Regs</div>
      <h1>Pilot Car Regulations</h1>
      <p>Save hours of surfing for state pilot car regulations. These are quick-reference guidelines only and are subject to change without notice — always confirm against the permit issued by the pertinent permit office before a move.</p>
    </div>
    <div class="content" style="max-width:1180px">
      <div class="search-row">
        <input type="search" placeholder="Search states or provinces&hellip;" aria-label="Search states or provinces" data-filter-input=".region-tile">
      </div>
      <div class="disclaimer" style="margin-bottom:20px">
        <strong>Always verify:</strong> Rules change often and vary by carrier, route, and load. Use these pages as a starting point, not a substitute for your permit.
      </div>
      <div class="panel">
        <h2>United States</h2>
        <div class="region-grid">{region_grid(US_STATES)}</div>
      </div>
      <div class="panel">
        <h2>Canada</h2>
        <div class="region-grid">{region_grid(CA_PROVINCES)}</div>
      </div>
    </div>
    """
    html_out = page_shell(base=base, title=f"Pilot Car Regulations by State | {SITE_NAME}",
                           meta_description="State-by-state and province-by-province pilot car and oversize load escort regulations guidelines.",
                           active_key="regulations", body_html=body, canonical_path="regulations/index.html",
                           breadcrumbs=[("Home", "index.html"), ("Pilot Car Regulations", None)])
    write("regulations/index.html", html_out)


from html.parser import HTMLParser


class _Sanitizer(HTMLParser):
    """Keep simple formatting from the rich-text editor; drop everything else.
    Text is always escaped, links must be web, email or phone links."""
    ALLOWED = {"p", "br", "h2", "h3", "h4", "ul", "ol", "li", "strong", "b", "em", "i", "a"}
    DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP_CONTENT:
            self.skip += 1; return
        if self.skip or tag not in self.ALLOWED:
            return
        if tag == "a":
            href = dict(attrs).get("href", "") or ""
            if re.match(r"^(https?://|mailto:|tel:)", href, re.I):
                ext = ' target="_blank" rel="noopener"' if href.lower().startswith("http") else ""
                self.out.append(f'<a href="{esc(href)}"{ext}>')
            else:
                self.out.append("<a>")
        elif tag == "br":
            self.out.append("<br>")
        else:
            self.out.append(f"<{tag}>")

    def handle_endtag(self, tag):
        if tag in self.DROP_CONTENT:
            self.skip = max(0, self.skip - 1); return
        if not self.skip and tag in self.ALLOWED and tag != "br":
            self.out.append(f"</{tag}>")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(esc(data))


def sanitize_html(raw):
    s = _Sanitizer()
    s.feed(raw or "")
    s.close()
    return "".join(s.out)


def render_reg_page(page, name):
    verified = (page.get("lastVerified") or "").strip()
    when = (f"Last checked {esc(verified)}." if verified
            else "This information comes from our previous website and hasn't been re-checked yet.")
    src = (page.get("sourceUrl") or "").strip()
    src_html = (f' <a href="{esc(src)}" target="_blank" rel="noopener">Official source</a>.'
                if re.match(r"^https?://", src) else "")
    return f"""
            <div class="disclaimer">
              <strong>Verify before you move:</strong> {when} Rules change often &mdash; always confirm with the
              {esc(name)} permit office before you dispatch.{src_html}
            </div>
            <div class="panel reg-body">{sanitize_html(page.get("body"))}</div>"""


def build_regulations_state_pages():
    for r in ALL_REGIONS:
        base = "../"
        slug = r["slug"]
        name = r["name"]
        page = REG_PAGES.get(slug)
        data = None if page else REGS.get(slug)
        if page:
            body_main = render_reg_page(page, name)
        elif data:
            qf = data["quickFacts"]
            esc_rules = "".join(f"<li>{esc(x)}</li>" for x in data["escortRequirements"]["rules"])
            body_main = f"""
            <div class="disclaimer">
              <strong>Verify before you move:</strong> {esc(data["disclaimer"])}
            </div>
            <div class="panel">
              <h2>Quick Facts</h2>
              <table class="listing-table">
                <tbody>
                  <tr><th style="width:220px">When a permit is needed</th><td>{esc(qf["permitNeeded"])}</td></tr>
                  <tr><th>Special information needed</th><td>{esc(qf["specialInfo"])}</td></tr>
                  <tr><th>Times of movement</th><td>{esc(qf["travelWindow"])}</td></tr>
                  <tr><th>Holiday restrictions</th><td>{esc(qf["holidayRestrictions"])}</td></tr>
                  <tr><th>Curfews</th><td>{esc(qf.get("curfews","—"))}</td></tr>
                </tbody>
              </table>
            </div>
            <div class="panel">
              <h2>When a Pilot / Escort Vehicle Is Required</h2>
              <p>Official reference: <a href="{esc(data["escortRequirements"]["sourceUrl"])}" target="_blank" rel="nofollow noopener">state administrative code &#8599;</a></p>
              <ul>{esc_rules}</ul>
            </div>
            <div class="panel">
              <h2>Equipment Requirements</h2>
              <p><strong>Vehicle:</strong> {esc(data["equipmentRequirements"]["vehicle"])}</p>
              <p><strong>Signs:</strong> {esc(data["equipmentRequirements"]["signs"])}</p>
              <p><strong>Lights:</strong> {esc(data["equipmentRequirements"]["lights"])}</p>
              <p><strong>Flags:</strong> {esc(data["equipmentRequirements"]["flags"])}</p>
              <p><strong>Additional equipment:</strong> {esc(data["equipmentRequirements"]["additional"])}</p>
            </div>
            <div class="panel">
              <h2>Operator Requirements</h2>
              <p>{esc(data["operatorRequirements"])}</p>
            </div>
            <div class="panel">
              <h2>Permit Office</h2>
              <p><strong>{esc(data["permitOffice"]["name"])}</strong><br>
              {esc(data["permitOffice"].get("address",""))}<br>
              Hours: {esc(data["permitOffice"]["hours"])}<br>
              Phone: <a href="tel:{re.sub(r'[^0-9+]','',data["permitOffice"]["phone"])}">{esc(data["permitOffice"]["phone"])}</a><br>
              {'Fax: ' + esc(data["permitOffice"]["fax"]) + '<br>' if data["permitOffice"].get("fax") else ''}
              {'OS/OW permit line: <a href="tel:'+re.sub(r'[^0-9+]','',data["permitOffice"]["osOwPermitPhone"])+'">'+esc(data["permitOffice"]["osOwPermitPhone"])+'</a><br>' if data["permitOffice"].get("osOwPermitPhone") else ''}
              <a href="{esc(data["permitOffice"]["url"])}" target="_blank" rel="nofollow noopener">Permit office website &#8599;</a></p>
            </div>
            <div class="panel">
              <h2>Road Conditions</h2>
              <p>Phone: <a href="tel:{re.sub(r'[^0-9+]','',data["roadConditions"]["phone"])}">{esc(data["roadConditions"]["phone"])}</a> &middot;
              <a href="{esc(data["roadConditions"]["url"])}" target="_blank" rel="nofollow noopener">Road conditions map &#8599;</a></p>
            </div>
            <div class="callout">Need a driver in {esc(name)}? <a href="../directory/{slug}.html">View the {esc(name)} pilot car directory</a>.</div>
            """
        else:
            body_main = f"""
            <div class="panel">
              <h2>{esc(name)} regulations coming soon</h2>
              <p>We haven't published a {esc(name)} summary yet. Until we do, please contact the {esc(name)} permit office or Department of Transportation directly for current pilot car requirements.</p>
              <p><a href="../directory/{slug}.html">View the {esc(name)} pilot car directory &rarr;</a></p>
            </div>
            """
        body = f"""
        <div class="page-header">
          <div class="eyebrow">Pilot Car Regulations</div>
          <h1>{esc(name)} Pilot Car Regulations</h1>
          <p>Guidelines for {esc(name)} pilot car, escort car, and flag car regulations. Always confirm current requirements with the permit office.</p>
        </div>
        <div class="content{' with-aside' if sponsor_aside(base) else ''}" style="max-width:1180px">
          <div class="main-stack">{body_main}{nearby_html(slug, "regulations")}</div>
          {sponsor_aside(base)}
        </div>
        """
        html_out = page_shell(base=base, title=f"{name} Pilot Car Regulations | {SITE_NAME}",
                               meta_description=f"{name} pilot car regulations and flag car regulations guidelines. Escort, permit, and equipment requirements.",
                               active_key="regulations", active_region_slug=slug, body_html=body,
                               canonical_path=f"regulations/{slug}.html",
                               breadcrumbs=[("Home", "index.html"), ("Pilot Car Regulations", "regulations/index.html"), (name, None)])
        write(f"regulations/{slug}.html", html_out)


# ---------------------------------------------------------------- RESOURCES
def load_hotel_chains():
    path = os.path.join(CONTENT, "hotel_chains.json")
    try:
        with open(path, encoding="utf-8") as f:
            chains = json.load(f).get("chains") or []
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"  WARNING: content/hotel_chains.json could not be read ({e})")
        return []
    return sorted([c for c in chains if c.get("name") and c.get("active", True) is not False],
                  key=lambda c: c["name"].lower())


def write_hotels_page(base):
    hotels = sorted(
        [h for st in HOTELS.values() for h in st["listings"] if is_live(h)],
        key=lambda h: (SLUG_TO_NAME.get(h["state"], h["state"]), (h.get("city") or "").lower(), h["name"].lower()))
    states_with = sorted({h["state"] for h in hotels}, key=lambda s: SLUG_TO_NAME.get(s, s))

    rows = []
    for h in hotels:
        st = h["state"]; st_name = SLUG_TO_NAME.get(st, st)
        name = esc(h["name"])
        if h.get("website"):
            name = f'<a href="{esc(h["website"])}" target="_blank" rel="nofollow noopener">{name}</a>'
        notes = " &middot; ".join(esc(n) for n in h.get("notes") or [])
        phone = f'<a href="{tel_href(h["phone"])}">{esc(h["phone"])}</a>' if h.get("phone") else ""
        rows.append(f"""<tr data-state="{esc(st)}" data-sort-state="{esc(st_name.lower())}"
            data-sort-city="{esc((h.get('city') or '').lower())}" data-sort-name="{esc(h['name'].lower())}">
          <td data-label="State"><a href="../directory/{esc(st)}.html">{esc(st_name)}</a></td>
          <td data-label="City" class="city">{esc(h.get("city") or "")}<div class="hotel-meta">{esc(h.get("address") or "")}</div></td>
          <td data-label="Hotel"><div class="co-name">{name}</div>{f'<div class="hotel-meta">{notes}</div>' if notes else ''}</td>
          <td data-label="Phone" class="phone">{phone}</td>
        </tr>""")

    state_opts = "".join(f'<option value="{esc(s)}">{esc(SLUG_TO_NAME.get(s, s))}</option>' for s in states_with)
    if rows:
        hotel_table = f"""
        <div class="table-tools">
          <label>Search <input type="search" placeholder="Hotel, city or state" data-table-search="hotel-table" autocomplete="off"></label>
          <label>State <select data-table-state="hotel-table"><option value="">All states</option>{state_opts}</select></label>
        </div>
        <p class="table-count" aria-live="polite" data-table-count="hotel-table">{len(rows)} hotels</p>
        <div class="table-scroll">
        <table class="data-table" id="hotel-table" data-sortable>
          <thead><tr>
            <th data-sort-key="state" aria-sort="ascending"><button type="button">State</button></th>
            <th data-sort-key="city"><button type="button">City</button></th>
            <th data-sort-key="name"><button type="button">Hotel</button></th>
            <th>Phone</th>
          </tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
        </div>
        <p class="table-empty" data-table-empty="hotel-table" hidden>No hotels match that search.</p>"""
    else:
        hotel_table = "<p>No hotels are listed yet.</p>"

    chains = load_hotel_chains()
    chain_rows = "".join(f"""<tr data-sort-name="{esc(c['name'].lower())}">
          <td data-label="Chain"><strong>{esc(c['name'])}</strong>{f'<span class="svc-chip deal-chip">{esc(c["note"])}</span>' if c.get('note') else ''}</td>
          <td data-label="Reservations" class="phone">{f'<a href="{tel_href(c["phone"])}">{esc(c["phone"])}</a>' if c.get('phone') else ''}</td>
          <td data-label="Website">{f'<a href="{esc(c["website"])}" target="_blank" rel="nofollow noopener">Visit site &#8599;</a>' if c.get('website') else ''}</td>
        </tr>""" for c in chains)
    chain_panel = f"""
      <div class="panel">
        <h2>Major hotel chains</h2>
        <p>Central reservation numbers. Some chains offer special rates for pilot car drivers &mdash; look for the tag.</p>
        <div class="table-tools">
          <label>Search chains <input type="search" placeholder="e.g. Motel 6" data-table-search="chain-table" autocomplete="off"></label>
        </div>
        <div class="table-scroll">
        <table class="data-table" id="chain-table" data-sortable>
          <thead><tr><th data-sort-key="name" aria-sort="ascending"><button type="button">Chain</button></th><th>Reservations</th><th>Website</th></tr></thead>
          <tbody>{chain_rows}</tbody>
        </table>
        </div>
        <p class="table-empty" data-table-empty="chain-table" hidden>No chains match that search.</p>
      </div>""" if chains else ""

    body = f"""
    <div class="page-header"><div class="eyebrow">Resources</div><h1>Find a Hotel</h1>
    <p>Pilot-car-friendly hotels by state, plus reservation numbers for the major chains. Search, pick a state, or tap a column heading to sort.</p></div>
    <div class="content" style="max-width:1100px">
      <div class="panel">
        <h2>Hotels that welcome pilot car drivers</h2>
        {hotel_table}
      </div>
      <div class="callout">
        Own a hotel that welcomes pilot car drivers? A highlighted listing in your city is available &mdash;
        see the <a href="../advertise/index.html">advertising page</a>. Hotel listings also appear on each state's directory page.
      </div>
      {chain_panel}
    </div>
    """
    write("resources/hotels.html", page_shell(base=base, title=f"Find a Hotel | {SITE_NAME}",
          meta_description="Pilot-car-friendly hotels by state, searchable and sortable, plus reservation numbers for major hotel chains.",
          active_key="resources", body_html=body, canonical_path="resources/hotels.html",
          breadcrumbs=[("Home", "index.html"), ("Resources", "resources/index.html"), ("Find a Hotel", None)]))


def build_resources():
    base = "../"

    hub_body = f"""
    <div class="page-header">
      <div class="eyebrow">Resources</div>
      <h1>Resources for Pilot Cars &amp; Oversize Loads</h1>
      <p>Practical tools for the road: conditions, weather, hotels, and truck stops in one place.</p>
    </div>
    <div class="content">
      <div class="feature-grid">
        <div class="feature-card"><h3>Road Conditions</h3><p>All the latest road conditions links and phone numbers on one page.</p><a href="road-conditions.html">View Road Conditions &rarr;</a></div>
        <div class="feature-card"><h3>Hotel List</h3><p>Discounted, pilot-car-friendly hotels along common routes.</p><a href="hotels.html">Find A Hotel &rarr;</a></div>
        <div class="feature-card"><h3>Truck Stop List</h3><p>Truck stop and fuel stop locations by state.</p><a href="truck-stops.html">View Truck Stops &rarr;</a></div>
        <div class="feature-card"><h3>Weather</h3><p>Check the weather anywhere, any state, with a forecast and moving animation map.</p><a href="https://www.accuweather.com/" target="_blank" rel="nofollow noopener">AccuWeather &#8599;</a></div>
        <div class="feature-card"><h3>Sunrise &amp; Sunset Tables</h3><p>Exact legal sunrise and sunset times for any city, per the US Naval Observatory — accepted at ports of entry in every state.</p><a href="https://www.sunrisesunset.com/USA/" target="_blank" rel="nofollow noopener">USA tables &#8599;</a> &middot; <a href="https://www.sunrisesunset.com/Canada/" target="_blank" rel="nofollow noopener">Canada tables &#8599;</a></div>
      </div>
    </div>
    """
    write("resources/index.html", page_shell(base=base, title=f"Resources | {SITE_NAME}",
          meta_description="Road conditions, weather, hotel lists, and truck stop directories for pilot car and oversize load travel.",
          active_key="resources", body_html=hub_body, canonical_path="resources/index.html",
          breadcrumbs=[("Home", "index.html"), ("Resources", None)]))

    rc_body = f"""
    <div class="page-header"><div class="eyebrow">Resources</div><h1>Road Conditions</h1>
    <p>All the latest road conditions links and phone numbers on one page, for your convenience and safety.</p></div>
    <div class="content" style="max-width:900px">
      <div class="panel">
        <h2>State &amp; Province Road Conditions</h2>
        <p>Each <a href="../regulations/index.html">state regulations page</a> lists that state's road-conditions phone number and link where migrated (New Mexico is fully populated as the pilot example). For states not yet migrated, contact the state DOT directly.</p>
      </div>
      <div class="panel">
        <h2>National Resources</h2>
        <ul>
          <li><a href="https://www.accuweather.com/" target="_blank" rel="nofollow noopener">AccuWeather &#8599;</a> — forecasts and moving animation weather maps, updated to the minute.</li>
          <li><a href="https://www.fhwa.dot.gov/" target="_blank" rel="nofollow noopener">Federal Highway Administration &#8599;</a></li>
        </ul>
      </div>
    </div>
    """
    write("resources/road-conditions.html", page_shell(base=base, title=f"Road Conditions | {SITE_NAME}",
          meta_description="Road conditions contact information for pilot car and oversize load travel by state.",
          active_key="resources", body_html=rc_body, canonical_path="resources/road-conditions.html",
          breadcrumbs=[("Home", "index.html"), ("Resources", "resources/index.html"), ("Road Conditions", None)]))

    # Hotels -- every state, searchable and sortable
    write_hotels_page(base)

    # Truck stops
    def ts_grid(regions):
        return "".join(f'<a class="region-tile" data-filter-text="{esc(r["name"])}" href="../directory/{r["slug"]}.html"><span>{esc(r["name"])}</span></a>' for r in regions)
    ts_body = f"""
    <div class="page-header"><div class="eyebrow">Resources</div><h1>Truck Stop &amp; Fuel Stop Directory</h1>
    <p>Use the list below to find a truck stop if you're a heavy-haul operator or pilot car driver looking for a place to park for the night or take on fuel.</p></div>
    <div class="content" style="max-width:1100px">
      <div class="disclaimer">
        <strong>{esc(TRUCKSTOPS["legacyNotice"])}</strong> Email <a href="mailto:{esc(TRUCKSTOPS["legacyContactEmail"])}">{esc(TRUCKSTOPS["legacyContactEmail"])}</a> to suggest a listing.
      </div>
      <div class="panel">
        <h2>Coming soon</h2>
        <p>State-by-state truck stop listings are on the way. In the meantime, the state DOT road conditions links on our <a href="road-conditions.html">road conditions page</a> list rest areas and truck parking for most states.</p>
      </div>
      <div class="panel">
        <h2>Jump to a State's Pilot Car Directory</h2>
        <div class="region-grid">{ts_grid(US_STATES)}</div>
      </div>
    </div>
    """
    write("resources/truck-stops.html", page_shell(base=base, title=f"Truck Stop Directory | {SITE_NAME}",
          meta_description="Truck stop and fuel stop directory by state for pilot car drivers and heavy-haul operators.",
          active_key="resources", body_html=ts_body, canonical_path="resources/truck-stops.html",
          breadcrumbs=[("Home", "index.html"), ("Resources", "resources/index.html"), ("Truck Stops", None)]))


# ---------------------------------------------------------------- ADVERTISE
def build_advertise():
    base = "../"
    tiers = [
        ("Basic Listing", "$29.99 / year", "Your company name, city, and phone number in the state directory of your choice. Free website link included."),
        ("Make Mine Bold", "$6.99 / month", "Bold-type treatment for an existing listing so it stands out from plain listings on the page."),
        ("4-State Bold Listing", "$12.99 / month", "Bold-type listing (with bolded city) across four states of your choice."),
        ("Single-State Super Listing", "$85.00 value", "A listing roughly 2/3 larger than a standard bold listing, linkable to a page with your company information."),
        ("4-State Super Listing", "$109.00 value", "The larger super-listing format, across four states of your choice."),
        ("Single-State Banner Ad", "$149.00 value", "A 2-column, 3-line full-color banner ad in the state of your choice, near the top of the page, linkable to your website."),
        ("4-State Banner Ad", "$299.00 value", "The full-color banner ad format across four states of your choice."),
        ("Expanded Bold Listing", "$14.99 / month", "Bold listing with a highlighted background for extra visibility."),
        ("Hotel Highlight Placement", "from $440/yr (annual)", "A 4-line highlighted placement for your hotel inserted into a state/city hotel list."),
    ]
    tier_rows = "".join(f"<tr><td>{esc(t[0])}</td><td>{esc(t[1])}</td><td>{esc(t[2])}</td></tr>" for t in tiers)
    body = f"""
    <div class="page-header">
      <div class="eyebrow">Advertise Here</div>
      <h1>US Pilot Cars Marketing Opportunities</h1>
      <p>Over half a million hits monthly, from an extremely targeted pilot car / oversize load audience. No setup fees. No long-term contracts. Cancel anytime.</p>
    </div>
    <div class="content" style="max-width:1100px">
      <div class="feature-grid" style="margin-bottom:20px">
        <div class="feature-card"><h3>Over 500K Hits / Month</h3><p>High-traffic, highly targeted for the pilot car industry.</p></div>
        <div class="feature-card"><h3>No Setup Fees</h3><p>No long-term contracts. Cancel anytime, for any reason.</p></div>
        <div class="feature-card"><h3>Free Website Link</h3><p>If you have a website, we'll link to it at no extra charge.</p></div>
      </div>
      <div class="panel">
        <h2>Listing &amp; Ad Tiers <span style="font-weight:400;font-size:.7em;color:var(--ink-muted)">(migrated from legacy pricing — verify current rates before publishing)</span></h2>
        <table class="listing-table">
          <thead><tr><th>Product</th><th>Price</th><th>What you get</th></tr></thead>
          <tbody>{tier_rows}</tbody>
        </table>
        <p style="margin-top:14px">Annual subscriptions typically include one month free versus paying monthly. All major credit cards accepted; billing is automatic monthly or annual.</p>
      </div>
      <div class="panel">
        <h2>Need a Specialty or Multi-State Ad?</h2>
        <p>Want a small ad on your home state? Want it on over 300 pages? Call for a free quote — no matter what kind of advertising you need.</p>
        <a class="btn btn-primary" href="tel:8662592750">Call 866-259-2750 for a Free Quote</a>
      </div>
      <div class="panel">
        <h2>Example: A Live Featured Listing</h2>
        <p>Here's how a state banner placement actually renders on a directory page:</p>
        {ad_card({"businessName":"Your Company Name","tier":"state_banner","description":"Your tagline / certifications / equipment go here.","city":"Your City, ST","services":["height_pole","route_survey"],"phone":"555-555-5555","website":"https://example.com","image":"assets/images/advertisements/placeholder-banner-wide.svg"}, base)}
      </div>
    </div>
    """
    write("advertise/index.html", page_shell(base=base, title=f"Advertise Your Pilot Car Company | {SITE_NAME}",
          meta_description="Advertising opportunities for pilot car and escort vehicle companies: bold listings, super listings, and banner ads by state.",
          active_key="advertise", body_html=body, canonical_path="advertise/index.html",
          breadcrumbs=[("Home", "index.html"), ("Advertise", None)]))


# ---------------------------------------------------------------- PRIVACY
# OWNER TO-DO (not shown to visitors): this page carries forward the old
# site's consent wording. Before launch, have it reviewed -- it now needs to
# mention Jotform and Square, which handle customer details at checkout.
def services_form_target():
    """Where the form sends. A private FormSubmit code (formAlias) is used if
    set -- it hides the email address from spammers -- otherwise the email."""
    alias = (SERVICES.get("formAlias") or "").strip()
    email = (SERVICES.get("inquiryEmail") or "").strip()
    live = bool(alias) or (bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)) and not email.lower().endswith("@example.com"))
    return (alias or email), live


def build_services():
    if not SERVICES.get("enabled", True):
        return
    base = ""
    target, live = services_form_target()
    if not live:
        print("  NOTE: design services form is waiting for a real email address (Pages CMS -> Design Services)")
    cards = "".join(
        f'<div class="svc-card"><h3>{esc(s.get("title", ""))}</h3><p>{esc(s.get("description", ""))}</p>'
        + (f'<div class="svc-price">{esc(s["startingPrice"])}</div>' if s.get("startingPrice") else "")
        + "</div>"
        for s in SERVICES.get("services") or [] if s.get("title"))
    options = "".join(f"<option>{esc(s.get('title'))}</option>" for s in SERVICES.get("services") or [] if s.get("title"))
    status = ("" if live else
              '<p class="form-note">Online inquiries open soon. In the meantime, call '
              '<a href="tel:8662592750">866-259-2750</a>.</p>')
    body = f"""
    <div class="page-header"><div class="eyebrow">Design Services</div><h1>{esc(SERVICES.get("headline"))}</h1>
      <p>{esc(SERVICES.get("intro"))}</p></div>
    <div class="content" style="max-width:900px">
      <div class="callout">{esc(SERVICES.get("relationshipNotice"))}</div>
      <div class="svc-grid">{cards}</div>
      <div class="panel">
        <h2>Tell us about your project</h2>
        {status}
        <form class="inquiry-form" action="https://formsubmit.co/{esc(target)}" method="POST">
          <input type="hidden" name="_subject" value="New design services inquiry from uspilotcars.com">
          <input type="hidden" name="_template" value="table">
          <input type="hidden" name="_next" value="{SITE_URL}/design-services-thanks.html">
          <div class="hp" aria-hidden="true"><label>Leave this empty <input type="text" name="_honey" tabindex="-1" autocomplete="off"></label></div>
          <div class="form-row">
            <label>Your name <input type="text" name="name" required autocomplete="name"></label>
            <label>Email <input type="email" name="email" required autocomplete="email"></label>
          </div>
          <div class="form-row">
            <label>Phone (optional) <input type="tel" name="phone" autocomplete="tel"></label>
            <label>Business name (optional) <input type="text" name="business" autocomplete="organization"></label>
          </div>
          <label>What do you need?
            <select name="service" required><option value="">Choose one</option>{options}<option>Something else</option></select>
          </label>
          <label>Tell us a little about it
            <textarea name="message" rows="6" required></textarea>
          </label>
          <button class="btn" type="submit"{"" if live else " disabled"}>Send my inquiry</button>
        </form>
      </div>
    </div>"""
    write("design-services.html", page_shell(base=base, title=f"Website & Advertisement Design | {SITE_NAME}",
          meta_description="Website, advertisement and logo design for pilot car companies, hotels and trucking businesses.",
          active_key="services", body_html=body, canonical_path="design-services.html",
          breadcrumbs=[("Home", "index.html"), ("Design Services", None)]))
    thanks = """
    <div class="page-header"><div class="eyebrow">Design Services</div><h1>Thanks &mdash; we got your message</h1>
      <p>We'll get back to you soon, usually within one business day.</p></div>
    <div class="content" style="max-width:900px"><p><a class="btn" href="index.html">Back to the directory</a></p></div>"""
    write("design-services-thanks.html", page_shell(base=base, title=f"Thanks | {SITE_NAME}",
          meta_description="Thanks for your inquiry.", active_key="services", body_html=thanks,
          canonical_path="design-services-thanks.html", breadcrumbs=[("Home", "index.html"), ("Thanks", None)]))


def build_lineup():
    """Ad lineup: every paid position in the exact order visitors see it,
    with each ad's order number. For checking 'who's on top' before and
    after a change. Not linked from the site and hidden from search engines."""
    base = ""

    def table(ads, show_pin=False):
        if not ads:
            return '<p class="hotel-meta">None right now.</p>'
        rows = "".join(
            f"<tr><td class='pos'>{i}</td><td><strong>{esc(a['businessName'])}</strong>"
            f"{'<div class=hotel-meta>' + esc(a['city']) + '</div>' if a.get('city') else ''}</td>"
            f"<td>{esc(a.get('package') or TIER_LABEL.get(a.get('tier'), ''))}</td>"
            f"<td>{esc(a.get('endDate') or '')}</td></tr>"
            for i, a in enumerate(ads, 1))
        return ("<div class='table-scroll'><table class='data-table lineup'><thead><tr><th>#</th><th>Advertiser</th>"
                "<th>What they bought</th><th>Last day shown</th></tr></thead><tbody>" + rows + "</tbody></table></div>")

    sections = [("Nationwide Sponsors &mdash; under the title of every page", table(sitewide_banners()))]
    state_blocks = []
    for r in ALL_REGIONS:
        lu = LINEUPS.get(r["slug"]) or {}
        sl = lineup_ads(lu.get("stateListings"), r["name"])
        su_e = lineup_entries(lu.get("superListings"), r["name"])
        su = [a for a, it in su_e if it.get("pinned")] + [a for a, it in su_e if not it.get("pinned")]
        pinned = [a for a in ads_for_placement(r["slug"]) if a.get("pinned")]
        if not (sl or su or pinned):
            continue
        state_blocks.append(f"""<details class="panel lineup-state"><summary><strong>{esc(r['name'])}</strong>
          <span class="hotel-meta">{len(sl)} state listings, {len(su)} super listings, {len(pinned)} pinned</span></summary>
          <h3>State listings</h3>{table(sl)}
          <h3>Super listings{(" &mdash; " + str(sum(1 for _, it in su_e if it.get("pinned"))) + " pinned to the top") if any(it.get("pinned") for _, it in su_e) else ""}</h3>{table(su)}
          <h3>Pinned to the top of the company list</h3>{table(pinned)}</details>""")

    body = f"""
    <div class="page-header"><div class="eyebrow">For the site owner</div><h1>Ad lineup</h1>
      <p>Every paid position, in the order visitors see it. To change the order, open
      <strong>Nationwide Sponsors</strong> or the state under <strong>State pages</strong> in the editor and
      move the ad up or down its list. Changes appear here and on the site a couple of minutes after saving.</p></div>
    <div class="content" style="max-width:1000px">
      {''.join(f'<div class="panel"><h2>{h}</h2>{b}</div>' for h, b in sections)}
      <h2 style="margin:28px 0 10px">By state</h2>
      {''.join(state_blocks) or '<p>No state has featured or pinned listings yet.</p>'}
    </div>"""
    html_out = page_shell(base=base, title=f"Ad lineup | {SITE_NAME}", meta_description="Ad lineup.",
                          active_key="", body_html=body, canonical_path="ad-lineup.html",
                          breadcrumbs=[("Home", "index.html"), ("Ad lineup", None)])
    html_out = html_out.replace("<head>", '<head>\n<meta name="robots" content="noindex, nofollow">', 1)
    write("ad-lineup.html", html_out)


def build_privacy():
    base = ""
    body = f"""
    <div class="page-header"><div class="eyebrow">Legal</div><h1>Privacy &amp; Security</h1></div>
    <div class="content" style="max-width:800px">
      <div class="panel">
        <p>By giving us your phone number or email address, you acknowledge that you may receive text or email messages related to your account (2 messages/month maximum). Message and data rates may apply. Reply STOP to opt out of future messages; your account will then be closed.</p>

      </div>
    </div>
    """
    write("privacy.html", page_shell(base=base, title=f"Privacy & Security | {SITE_NAME}",
          meta_description="Privacy and security policy for US Pilot Cars.",
          active_key="privacy", body_html=body, canonical_path="privacy.html",
          breadcrumbs=[("Home", "index.html"), ("Privacy", None)]))


# ---------------------------------------------------------------- LEGACY REDIRECTS
# Old flat-file URL -> new nested URL. Static entries are pages that don't
# follow the per-state pattern; the per-state patterns are generated below.
LEGACY_STATIC = {
    "pilot_car_directory.html": "directory/index.html",
    "state_pilot_car_guidelines.html": "regulations/index.html",
    "marketing_opportunities.html": "advertise/index.html",
    "us_pilot_car_privacy.html": "privacy.html",
    "truck_stop.html": "resources/truck-stops.html",
    "find_a_hotel.html": "resources/hotels.html",
    "road_conditions_information.html": "resources/road-conditions.html",
    "thanks-basic.html": "advertise/index.html",
    "purchasethanks.html": "advertise/index.html",

    # Found in the server copy (htdocs) but missing from the original map.
    # Old order/thank-you/demo pages -> the Advertise page.
    "BASIC_Listing.html": "advertise/index.html",
    "freelisting.html": "advertise/index.html",
    "freelistingreturn.html": "advertise/index.html",
    "thanks.html": "advertise/index.html",
    "thanks4.html": "advertise/index.html",
    "thanks-superbold.html": "advertise/index.html",
    "thankspermit.html": "advertise/index.html",
    "thankspurchase.html": "advertise/index.html",
    "thankyou.html": "advertise/index.html",
    "special_offer.html": "advertise/index.html",
    "right_column_ad.html": "advertise/index.html",
    "ad_demo.html": "advertise/index.html",
    "addemo2.html": "advertise/index.html",
    "demo.html": "advertise/index.html",
    "demo_page.html": "advertise/index.html",
    "demo_page2.html": "advertise/index.html",
    "itsdemo.html": "advertise/index.html",
    # Old single-company and duplicate pages -> their state's directory.
    "bandb.html": "directory/alabama.html",            # B and B Pilot Car Service (AL)
    "golddust.html": "directory/louisiana.html",       # Gold Dust Pilot Cars (LA)
    "florida_pilot_car2.html": "directory/florida.html",
    "pilot_car_directory-test.html": "directory/index.html",
    "site_search.html": "directory/index.html",
    "route_surveys.html": "directory/index.html",
    # Guides
    "quebec_guidelines.html": "regulations/quebec.html",
    "pilot_car_service_guide.html": "regulations/index.html",
    "oversize_load_permits.html": "resources/index.html",
    "pilot_car_store.html": "index.html",
    # Old trade-fair travel pages (unrelated to pilot cars) -> home.
    "domotex_carpet_fair.html": "index.html",
    "ipm_fair_essen.html": "index.html",
    "ish_fair_frankfurt.html": "index.html",
    "ism_confectionary_fair.html": "index.html",
    "iwa_sporting_arms_fair.html": "index.html",
}

# Legacy directory-page filenames that don't match the simple
# "{name}_pilot_car.html" pattern.
LEGACY_DIRECTORY_OVERRIDES = {
    "tennessee": "tennesee_pilot_car.html",       # legacy misspelling
    "vermont": "vermont_pilot_cars.html",          # legacy plural form
    "alberta": "alberta_pilot_cars.html",
    "british-columbia": "british_columbia_pilot_cars.html",
    "nova-scotia": "nova_scotia_pilot_cars.html",
    "ontario": "ontario_pilot_car.html",
    "quebec": "quebec_pilot_cars.html",
    "saskatchewan": "saskatchewan_pilot_cars.html",
    "yukon": "page211.html",
}
# Provinces with no legacy directory URL (plain, unlinked text on the old page)
LEGACY_DIRECTORY_NO_URL = {"manitoba", "new-brunswick", "newfoundland-and-labrador", "northwest-territories"}

LEGACY_REGULATIONS_OVERRIDES = {
    "tennessee": "tennesee_pilot_car_regulations.html",  # legacy misspelling
    "nevada": "nevada_pilot_car_mexico.html",             # legacy odd filename
    "alberta": "page212.html",
    "british-columbia": "page213.html",
    "manitoba": "page214.html",
    "northwest-territories": "page217.html",
    "nova-scotia": "page218.html",
    "ontario": "page219.html",
    "saskatchewan": "page197.html",
    "yukon": "page222.html",
}
LEGACY_REGULATIONS_NO_URL = {"new-brunswick", "newfoundland-and-labrador", "quebec"}

# The legacy truck stop hub linked Washington and West Virginia to the
# DIRECTORY filenames by mistake. The previous rebuild copied that typo, so
# the old Washington and West Virginia directory addresses were being sent
# to the truck stop page. Those filenames belong to the directory; truck
# stops use the standard pattern like every other state.
LEGACY_TRUCK_STOP_OVERRIDES = {}
# States with no legacy truck-stop URL at all (not present in the legacy hub list)
LEGACY_TRUCK_STOP_NO_URL = {"hawaii"}


REDIRECTS = {}


def redirect_stub(old_path, new_relpath):
    """Record a permanent (301) redirect for Cloudflare's _redirects file.

    Real server redirects replace the old meta-refresh stub pages: faster
    for visitors and they pass search ranking properly. If two rules ever
    claim the same old address, the first one wins and the build says so
    rather than silently overwriting (which is how the WA/WV bug hid)."""
    target = "/" + new_relpath
    if target.endswith("index.html"):
        target = target[: -len("index.html")]
    elif target.endswith(".html"):
        target = target[: -len(".html")]
    if old_path in REDIRECTS and REDIRECTS[old_path] != target:
        print(f"  WARNING: /{old_path} already redirects to {REDIRECTS[old_path]}; ignoring {target}")
        return old_path, new_relpath
    REDIRECTS[old_path] = target
    return old_path, new_relpath


def write_redirects_file():
    lines = ["# Generated by build.py -- do not edit by hand.",
             "# Old uspilotcars.com addresses -> new pages (permanent redirects)."]
    for old, target in sorted(REDIRECTS.items()):
        lines.append(f"/{old} {target} 301")
        # Cloudflare may strip .html before matching; cover both forms.
        if old.endswith(".html"):
            lines.append(f"/{old[:-5]} {target} 301")
    write("_redirects", "\n".join(lines) + "\n")
    return len(REDIRECTS)


def build_legacy_redirects():
    migration_rows = []

    for old, new in LEGACY_STATIC.items():
        redirect_stub(old, new)
        migration_rows.append((old, new, "Yes", "Static page, moved into a section folder."))

    for r in US_STATES + CA_PROVINCES:
        slug = r["slug"]
        underscored = slug.replace("-", "_")

        # Directory page
        if slug in LEGACY_DIRECTORY_NO_URL:
            pass
        else:
            old_dir = LEGACY_DIRECTORY_OVERRIDES.get(slug, f"{underscored}_pilot_car.html")
            redirect_stub(old_dir, f"directory/{slug}.html")
            note = "Legacy filename irregularity preserved in mapping." if slug in LEGACY_DIRECTORY_OVERRIDES else "Standard per-state pattern."
            migration_rows.append((old_dir, f"directory/{slug}.html", "Yes", note))

        # Regulations page
        if slug in LEGACY_REGULATIONS_NO_URL:
            pass
        else:
            old_reg = LEGACY_REGULATIONS_OVERRIDES.get(slug, f"{underscored}_pilot_car_regulations.html")
            redirect_stub(old_reg, f"regulations/{slug}.html")
            note = "Legacy filename irregularity preserved in mapping." if slug in LEGACY_REGULATIONS_OVERRIDES else "Standard per-state pattern."
            migration_rows.append((old_reg, f"regulations/{slug}.html", "Yes", note))

        # Truck stop page (US only in legacy site)
        if r in US_STATES and slug not in LEGACY_TRUCK_STOP_NO_URL:
            old_ts = LEGACY_TRUCK_STOP_OVERRIDES.get(slug, f"{underscored}_truck_stops.html")
            redirect_stub(old_ts, "resources/truck-stops.html")
            migration_rows.append((old_ts, "resources/truck-stops.html", "Yes",
                                    "Per-state truck stop pages consolidated into one directory; add real per-state data to data/truck_stops.json."))

    return migration_rows


def write_migration_map(rows):
    lines = [
        "# URL Migration Map",
        "",
        "Generated by `build.py` from the same data that drives the redirect stubs, so this file and the live redirects can never drift apart. Re-run `python3 build.py` after any change to `data/states.json` and this file regenerates automatically.",
        "",
        "Every row below becomes a permanent (301) server redirect in `dist/_redirects`, which Cloudflare Pages applies before serving any page.",
        "",
        "| Old URL | New URL | Redirected? | Notes |",
        "|---|---|---|---|",
    ]
    for old, new, redirect, note in rows:
        lines.append(f"| `/{old}` | `/{new}` | {redirect} | {note} |")
    lines.append("")
    lines.append("## Pages with no legacy URL to preserve")
    lines.append("")
    lines.append("These new pages didn't exist as individual URLs on the legacy site (they were unlinked text, or consolidated into a hub page), so there is nothing to redirect *from*:")
    lines.append("")
    for slug in sorted(LEGACY_DIRECTORY_NO_URL):
        lines.append(f"- `/directory/{slug}.html` (province had no linked legacy directory page)")
    for slug in sorted(LEGACY_REGULATIONS_NO_URL):
        lines.append(f"- `/regulations/{slug}.html` (province had no linked legacy regulations page)")
    lines.append(f"- `/resources/truck-stops.html` for Hawaii (not present in the legacy truck stop hub)")
    lines.append("")
    write("MIGRATION_MAP.md", "\n".join(lines), into=ROOT)


def build_root_files():
    write("robots.txt", "User-agent: *\nAllow: /\nSitemap: " + SITE_URL + "/sitemap.xml\n")
    urls = ["index.html", "directory/index.html", "regulations/index.html",
            "resources/index.html", "resources/road-conditions.html", "resources/hotels.html",
            "resources/truck-stops.html", "advertise/index.html", "privacy.html"]
    if SERVICES.get("enabled", True):
        urls.append("design-services.html")
    for r in ALL_REGIONS:
        urls.append(f"directory/{r['slug']}.html")
        urls.append(f"regulations/{r['slug']}.html")
    entries = "\n".join(f"  <url><loc>{canonical_url(u)}</loc></url>" for u in urls)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n')

    write("404.html", page_shell(base="", title=f"Page Not Found | {SITE_NAME}",
          meta_description="Page not found.",
          active_key="home",
          body_html=f"""<div class="page-header"><h1>Page Not Found</h1><p>That page moved or never existed. Try the directory or regulations index.</p></div>
          <div class="content"><a class="btn btn-primary" href="index.html">Back to Home</a> <a class="btn btn-outline" href="directory/index.html">Pilot Car Directory</a></div>""",
          canonical_path="404.html"))


def prepare_output():
    """Start from an empty dist/ every time, then copy the static assets."""
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(os.path.join(ROOT, "assets"), os.path.join(OUT, "assets"),
                    ignore=shutil.ignore_patterns("file.txt", ".DS_Store"))


if __name__ == "__main__":
    prepare_output()
    build_home()
    build_directory_hub()
    build_directory_state_pages()
    build_regulations_hub()
    build_regulations_state_pages()
    build_resources()
    build_advertise()
    build_privacy()
    build_services()
    build_lineup()
    build_root_files()
    migration_rows = build_legacy_redirects()
    write_migration_map(migration_rows)
    n = write_redirects_file()
    print(f"Build complete -> dist/   ({n} old addresses redirected)")
