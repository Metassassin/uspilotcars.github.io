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
import re
import html
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")

SITE_NAME = "US Pilot Cars"
SITE_TAGLINE = "Pilot Car & Escort Vehicle Directory"
SITE_URL = "https://uspilotcars.example.github.io"  # update after you know your Pages URL

# ---------------------------------------------------------------- load data
with open(os.path.join(DATA, "states.json")) as f:
    STATES = json.load(f)
with open(os.path.join(DATA, "advertisements.json")) as f:
    ADS = json.load(f)["listings"]
with open(os.path.join(DATA, "regulations.json")) as f:
    REGS = json.load(f)["states"]
with open(os.path.join(DATA, "hotels.json")) as f:
    HOTELS = json.load(f)["states"]
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


def esc(s):
    return html.escape(s, quote=True) if isinstance(s, str) else s


def region_slugify_check(slug):
    assert re.match(r"^[a-z-]+$", slug), slug


# ---------------------------------------------------------------- fragments
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
        <a href="{base}index.html" aria-label="{SITE_NAME} home">
          <img class="badge" src="{base}assets/images/branding/logo-mark.svg" alt="" width="38" height="38">
          <span class="brand-text">{SITE_NAME}<small>{SITE_TAGLINE}</small></span>
        </a>
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
      <a class="brand" href="{base}index.html">
        <img class="badge" src="{base}assets/images/branding/logo-mark.svg" alt="" width="28" height="28" style="width:28px;height:28px;border-radius:6px;">
        {SITE_NAME}
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
<link rel="canonical" href="{SITE_URL}/{canonical_path}">
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
  {body_html}
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


def write(path, contents):
    full = os.path.join(ROOT, path)
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
      <div class="panel" style="margin-bottom:24px">
        <h2 style="margin-bottom:14px">Sitewide Featured Advertisers</h2>
        <div class="feature-grid">
          {"".join(ad_card(a, base) for a in ads_for_placement("sitewide") if a["tier"] == "global_banner")}
        </div>
      </div>
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
    return sorted([a for a in ADS if slug in a.get("placement", [])], key=lambda a: a.get("priority", 999))


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


def build_directory_state_pages():
    for r in ALL_REGIONS:
        base = "../"
        slug = r["slug"]
        name = r["name"]
        region_ads = ads_for_placement(slug)
        banner_ads = [a for a in region_ads if a["tier"] in ("state_banner", "global_banner")]
        other_ads = [a for a in region_ads if a["tier"] not in ("state_banner", "global_banner")]

        if region_ads:
            listing_rows = "".join(
                f"""<tr>
                  <td>{esc(a.get("city") or "")}</td>
                  <td>{esc(a["businessName"])}{' <span class="svc-chip" style="margin-left:6px">' + ' '.join(SERVICE_LABELS.get(s,s)[:1] for s in a.get('services',[])) + '</span>' if a.get('services') else ''}</td>
                  <td class="phone"><a href="tel:{re.sub(r'[^0-9+]','',a.get('phone') or '')}">{esc(a.get('phone') or '')}</a></td>
                </tr>"""
                for a in sorted(region_ads, key=lambda a: a.get("priority", 999))
            )
            table_html = f"""
            <div class="panel">
              <h2>{esc(name)} Pilot Car Listings</h2>
              <table class="listing-table">
                <thead><tr><th>City</th><th>Company</th><th>Phone</th></tr></thead>
                <tbody>{listing_rows}</tbody>
              </table>
            </div>
            """
            cards_html = "".join(ad_card(a, base) for a in other_ads)
            banners_html = "".join(ad_card(a, base) for a in banner_ads)
            reg_note = ""
            if slug in REGS:
                reg_note = f'<div class="callout" style="margin-top:14px">Planning a move through {esc(name)}? Review the <a href="../regulations/{slug}.html">{esc(name)} pilot car regulations</a> before you dispatch.</div>'
            main_content = f"""
              {banners_html}
              {table_html}
              <div class="panel">
                <h2>Featured &amp; Additional Listings</h2>
                <div class="feature-grid">{cards_html or '<p>No additional featured listings for this state yet.</p>'}</div>
              </div>
              {reg_note}
            """
        else:
            main_content = f"""
            <div class="panel">
              <h2>Listings Coming Soon</h2>
              <p><strong>Migration placeholder:</strong> {esc(name)} pilot car listings have not yet been migrated from the legacy site into this data set. This is a structural placeholder, not a claim that no companies operate here.</p>
              <p>If you operate a pilot car service in {esc(name)}, <a href="../advertise/index.html">get listed here</a>, or call <a href="tel:8662592750">866-259-2750</a> for a free quote.</p>
            </div>
            """

        body = f"""
        <div class="page-header">
          <div class="eyebrow">Pilot Car Directory</div>
          <h1>{esc(name)} Pilot Car Service</h1>
          <p>Find {esc(name)} pilot car, escort car, and flag car companies. Call directly or visit a company's website for a quote.</p>
        </div>
        <div class="content" style="max-width:1180px">
          {main_content}
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
            has = r["slug"] in REGS
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


def build_regulations_state_pages():
    for r in ALL_REGIONS:
        base = "../"
        slug = r["slug"]
        name = r["name"]
        data = REGS.get(slug)
        if data:
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
              <h2>Not Yet Migrated</h2>
              <p><strong>Migration placeholder:</strong> {esc(name)}'s detailed regulation content has not yet been migrated from the legacy site into this data set. We deliberately show this notice instead of guessing at regulatory requirements.</p>
              <p>For {esc(name)}, contact the state or provincial Department of Transportation / permit office directly, or check the legacy guideline page during migration.</p>
              <p><a href="../directory/{slug}.html">View the {esc(name)} pilot car directory &rarr;</a></p>
            </div>
            """
        body = f"""
        <div class="page-header">
          <div class="eyebrow">Pilot Car Regulations</div>
          <h1>{esc(name)} Pilot Car Regulations</h1>
          <p>Guidelines for {esc(name)} pilot car, escort car, and flag car regulations. Always confirm current requirements with the permit office.</p>
        </div>
        <div class="content" style="max-width:900px">{body_main}</div>
        """
        html_out = page_shell(base=base, title=f"{name} Pilot Car Regulations | {SITE_NAME}",
                               meta_description=f"{name} pilot car regulations and flag car regulations guidelines. Escort, permit, and equipment requirements.",
                               active_key="regulations", active_region_slug=slug, body_html=body,
                               canonical_path=f"regulations/{slug}.html",
                               breadcrumbs=[("Home", "index.html"), ("Pilot Car Regulations", "regulations/index.html"), (name, None)])
        write(f"regulations/{slug}.html", html_out)


# ---------------------------------------------------------------- RESOURCES
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

    # Hotels
    tx = HOTELS.get("texas", {}).get("listings", [])
    tx_rows = "".join(f"""
      <tr><td>{esc(h["city"])}</td><td>{esc(h["name"])}</td><td>{esc(h["address"])}</td>
      <td class="phone"><a href="tel:{re.sub(r'[^0-9+]','',h['phone'])}">{esc(h["phone"])}</a></td>
      <td>{', '.join(esc(n) for n in h.get("notes",[]))}</td></tr>""" for h in tx)
    hotel_body = f"""
    <div class="page-header"><div class="eyebrow">Resources</div><h1>Hotel List</h1>
    <p>Need a motel room on the road? Discounted, pet-friendly, pilot-car-friendly hotel listings by state.</p></div>
    <div class="content" style="max-width:1000px">
      <div class="panel">
        <h2>Texas</h2>
        <table class="listing-table">
          <thead><tr><th>City</th><th>Hotel</th><th>Address</th><th>Phone</th><th>Notes</th></tr></thead>
          <tbody>{tx_rows}</tbody>
        </table>
      </div>
      <div class="callout">
        Hotel owner? A highlighted 4-line placement in your city is available — see the <a href="../advertise/index.html">advertising page</a> for current rates.
      </div>
      <div class="panel">
        <h2>Other States</h2>
        <p><strong>Migration placeholder:</strong> additional state hotel lists have not yet been migrated from the legacy site. Add them to <code>data/hotels.json</code> and re-run <code>build.py</code>.</p>
      </div>
    </div>
    """
    write("resources/hotels.html", page_shell(base=base, title=f"Hotel List | {SITE_NAME}",
          meta_description="Discounted and pilot-car-friendly hotel listings by state for oversize load travel.",
          active_key="resources", body_html=hotel_body, canonical_path="resources/hotels.html",
          breadcrumbs=[("Home", "index.html"), ("Resources", "resources/index.html"), ("Hotel List", None)]))

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
        <h2>Migration Placeholder</h2>
        <p>Individual truck stop listings were not captured in the initial audit and are marked as a placeholder rather than invented. Populate <code>data/truck_stops.json</code> per state as listings are migrated or sold, then re-run <code>build.py</code>.</p>
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
def build_privacy():
    base = ""
    body = f"""
    <div class="page-header"><div class="eyebrow">Legal</div><h1>Privacy &amp; Security</h1></div>
    <div class="content" style="max-width:800px">
      <div class="panel">
        <p>By giving us your phone number or email address, you acknowledge that you may receive text or email messages related to your account (2 messages/month maximum). Message and data rates may apply. Reply STOP to opt out of future messages; your account will then be closed.</p>
        <p><strong>Migration placeholder:</strong> this page carries forward the legacy site's consent language. Replace with your full privacy policy text as part of migration, and have it reviewed for your current SMS/email vendor and applicable law.</p>
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

LEGACY_TRUCK_STOP_OVERRIDES = {
    "washington": "washington_pilot_car.html",   # legacy hub linked the wrong file
    "west-virginia": "west_virginia_pilot_car.html",
}
# States with no legacy truck-stop URL at all (not present in the legacy hub list)
LEGACY_TRUCK_STOP_NO_URL = {"hawaii"}


def redirect_stub(old_path, new_relpath):
    depth = old_path.count("/")
    base = "../" * depth if depth else ""
    target = base + new_relpath
    html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{SITE_URL}/{new_relpath}">
<title>Redirecting… | {SITE_NAME}</title>
</head>
<body>
<p>This page has moved. <a href="{target}">Continue to the new page &rarr;</a></p>
</body>
</html>
"""
    write(old_path, html_out)
    return old_path, new_relpath


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
        "Every row below has a real, working redirect stub committed at the OLD URL path (a static HTML file with a `<meta http-equiv=\"refresh\">` and a `rel=\"canonical\"` pointing at the NEW URL). This is the standard way to preserve SEO equity on a host, like GitHub Pages, that has no server-side redirect config.",
        "",
        "| Old URL | New URL | Redirect Stub Committed? | Notes |",
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
    write("MIGRATION_MAP.md", "\n".join(lines))


def build_root_files():
    write("robots.txt", "User-agent: *\nAllow: /\nSitemap: " + SITE_URL + "/sitemap.xml\n")
    urls = ["index.html", "directory/index.html", "regulations/index.html",
            "resources/index.html", "resources/road-conditions.html", "resources/hotels.html",
            "resources/truck-stops.html", "advertise/index.html", "privacy.html"]
    for r in ALL_REGIONS:
        urls.append(f"directory/{r['slug']}.html")
        urls.append(f"regulations/{r['slug']}.html")
    entries = "\n".join(f"  <url><loc>{SITE_URL}/{u}</loc></url>" for u in urls)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{entries}\n</urlset>\n')

    write("404.html", page_shell(base="", title=f"Page Not Found | {SITE_NAME}",
          meta_description="Page not found.",
          active_key="home",
          body_html=f"""<div class="page-header"><h1>Page Not Found</h1><p>That page moved or never existed. Try the directory or regulations index.</p></div>
          <div class="content"><a class="btn btn-primary" href="index.html">Back to Home</a> <a class="btn btn-outline" href="directory/index.html">Pilot Car Directory</a></div>""",
          canonical_path="404.html"))


if __name__ == "__main__":
    build_home()
    build_directory_hub()
    build_directory_state_pages()
    build_regulations_hub()
    build_regulations_state_pages()
    build_resources()
    build_advertise()
    build_privacy()
    build_root_files()
    migration_rows = build_legacy_redirects()
    write_migration_map(migration_rows)
    print(f"Build complete. {len(migration_rows)} legacy redirect stubs written.")
