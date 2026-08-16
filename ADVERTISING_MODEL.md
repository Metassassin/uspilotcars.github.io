# Advertising Model

Advertising is a core business function of this site, not incidental content. This document explains how ads are represented, how they render, and exactly how to add one.

## Data, not markup

Every advertisement is one JSON object in `data/advertisements.json`, not hand-written HTML scattered across pages. `build.py` reads that file and renders each ad into the correct tier's markup, on every page where it's placed.

```json
{
  "id": "your-company-slug",
  "businessName": "Your Company Name",
  "tier": "state_banner",
  "placement": ["new-mexico", "texas"],
  "image": "assets/images/advertisements/your-company.jpg",
  "description": "Your tagline, certifications, or equipment.",
  "city": "Your City",
  "state": "New Mexico",
  "phone": "555-555-5555",
  "phone2": null,
  "email": "you@example.com",
  "website": "https://example.com",
  "externalUrl": "https://example.com",
  "services": ["height_pole", "route_survey"],
  "featured": true,
  "priority": 1,
  "sourceStatus": "migrated"
}
```

| Field | Meaning |
|---|---|
| `tier` | `global_banner`, `state_banner`, `super_listing`, `bold_listing`, or `basic_listing` — controls visual weight and where it can appear (see pricing below). |
| `placement` | List of state/province slugs, and/or `"sitewide"` for the highest tier. This is what makes 4-state (or sitewide) ad packages a one-line change. |
| `services` | Any of `height_pole`, `route_survey`, `multi_car`, `steering` — rendered as chips, replacing the legacy site's superscript numbers. |
| `priority` | Lower numbers render first within a tier. |
| `sourceStatus` | `migrated` (pulled from the legacy site during the 2026-08-16 audit) or `placeholder` (new, not yet verified) — purely an internal bookkeeping field, not shown to visitors. |

## Ad tiers, largest to smallest

| Tier | Legacy equivalent | Where it can appear | Visual treatment |
|---|---|---|---|
| `global_banner` | Sitewide banner ad | `placement: ["sitewide"]` — every page | Full-width image banner, amber top border, first position |
| `state_banner` | Single/4-state banner ad | One or more state slugs | Full-width image banner within that state's directory page |
| `super_listing` | Single/4-state super listing | One or more state slugs | Card with image, larger type |
| `bold_listing` | "Make Mine Bold" / bold listing | One or more state slugs | Bold company name, left accent bar, no image required |
| `basic_listing` | Basic listing | One or more state slugs | Compact row in the plain listing table only |

## Current pricing (migrated from the legacy Advertise page — verify before publishing)

See the rendered table on `/advertise/index.html` (also embedded in `build.py`) for the full list. Headline figures: Basic Listing $29.99/yr, Make Mine Bold $6.99/mo, 4-State Bold $12.99/mo, Single-State Super Listing ($85 value), 4-State Super Listing ($109 value), Single-State Banner ($149 value), 4-State Banner ($299 value), Expanded Bold Listing $14.99/mo, Hotel highlight placements from $440/yr annual. These were transcribed from the live site and should be reconfirmed with the owner before going live — pricing is exactly the kind of detail that changes without the website necessarily reflecting it yet.

## How to add a new advertiser

1. **Add the image.** Drop the creative into `assets/images/advertisements/` (e.g. `assets/images/advertisements/acme-pilot-cars.jpg`). Keep banner creatives roughly 16:5 to 16:6, everything else can be any reasonable size — the CSS crops responsively.
2. **Add an entry to `data/advertisements.json`.** Copy the schema above, fill in the business's real details, and don't invent anything — leave a field `null` if you don't have it yet.
3. **Set `placement`.** One state slug for a single-state package, several for a multi-state package, `"sitewide"` for the top tier.
4. **Set `tier`** to match what they purchased.
5. **Run `python3 build.py`** from the repository root. This regenerates every directory page that references the new ad.
6. **Commit and push.** GitHub Pages picks up the change automatically (see `README.md` for deployment).

No template editing, no HTML, no hunting through dozens of files — one JSON object in, `build.py` out.
