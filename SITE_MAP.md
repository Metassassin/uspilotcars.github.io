# Site Map — Old Structure vs. New Structure

## Legacy site (audited 2026-08-16 at uspilotcars.com)

- **Home** (`index.html`) — hero, sitewide banner ads, sidebar ad ("C B Piloting"), road conditions/weather/hotel promo blocks, Texas hotel sample, footer state links.
- **Pilot Car Directory** (`pilot_car_directory.html`) — hub linking to 50 US states (directory pages, minus a working Hawaii page) and 11 Canadian provinces.
  - Per-state pages (`{state}_pilot_car.html`) — mix of large banner ads, "super listing" ads, bold listings, and a plain table of city / company / phone, with superscript codes for services (height pole, route survey, multiple cars, steering).
- **Pilot Car Regulations** (`state_pilot_car_guidelines.html`) — hub linking to 49 US states + 8 Canadian provinces/territories (some as oddly-numbered legacy CMS pages, e.g. `page212.html`).
  - Per-state pages (`{state}_pilot_car_regulations.html`) — quick facts, escort requirements, equipment requirements, permit office contact, road conditions number.
- **Advertise Here** (`marketing_opportunities.html`) — a la carte pricing for bold listings, super listings, and banner ads, single-state or 4-state, monthly or annual, sold via PayPal subscription buttons.
- **Hotel List** (`find_a_hotel.html`) — hotel listings by state (sample seen: Texas), sold as "red fill" 4-line highlighted placements.
- **Truck Stop List** (`truck_stop.html`) — hub linking to per-state truck stop pages.
- **Road Conditions** (`road_conditions_information.html`) — links/phone numbers by state.
- **Privacy & Security** (`us_pilot_car_privacy.html`) — SMS/consent language.
- **Listing Update / thank-you pages** (`thanks-basic.html`, `purchasethanks.html`).
- Sitewide recurring ad placements (appear on every page): North American Transport Services (the operator's own multi-service banner), NY Truck Escorts & Permits, C B Piloting Services, plus outbound links to Facebook, Vidalia Dispatch, and Cayias.

## New site

```
/                              Home — hero, sitewide featured advertisers, quick links
/directory/                    Pilot Car Directory hub (US + Canada region grid, searchable)
/directory/{state}.html        Per-state directory: banner ads → compact listing table → other ads
/regulations/                  Pilot Car Regulations hub (US + Canada region grid, searchable)
/regulations/{state}.html      Per-state regulations: quick facts, escort/equipment rules, permit office
/resources/                    Resources hub
/resources/road-conditions.html
/resources/hotels.html         Hotel list by state (Texas fully migrated as the sample)
/resources/truck-stops.html    Truck stop directory framework + state jump list
/advertise/                    Advertising tiers, pricing, and a live example ad card
/privacy.html                  Privacy & security
/404.html                      Not-found page
{legacy-filename}.html         173 redirect stubs at every old flat URL (see MIGRATION_MAP.md)
```

## Mapping at a glance

| Legacy section | New section | Structural change |
|---|---|---|
| Home | `/` | Same job (orientation + top links), rebuilt with the sidebar + hero pattern |
| Pilot Car Directory + 50-ish per-state pages | `/directory/` + `/directory/{state}.html` | Same page-per-state model, now generated from `data/advertisements.json` and `data/states.json` instead of hand-authored HTML |
| Pilot Car Regulations + per-state pages | `/regulations/` + `/regulations/{state}.html` | Same page-per-state model, generated from `data/regulations.json` |
| Advertise Here | `/advertise/` | Same pricing tiers, restyled as a proper rate card with a live example |
| Hotel List | `/resources/hotels.html` | Same content, moved under Resources |
| Truck Stop List + per-state pages | `/resources/truck-stops.html` | Consolidated to one page + a state jump list; per-state data can be reintroduced via `data/truck_stops.json` |
| Road Conditions | `/resources/road-conditions.html` | Moved under Resources; per-state numbers live on each regulations page |
| Privacy & Security | `/privacy.html` | Same content, carried forward verbatim as a placeholder for legal review |
