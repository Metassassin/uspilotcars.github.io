# US Pilot Cars — Website

A directory of pilot car companies, hotels, and paid advertisements across
the US and Canada.

## How it works

```
data/*.json  ──►  build.py  ──►  dist/  ──►  Cloudflare Pages  ──►  uspilotcars.com
(the content)    (turns content   (the finished
                  into pages)      website)
```

- **Content** lives in `data/` — advertisements, hotels, regulations.
- **`build.py`** turns that content into web pages. Nobody runs it by hand:
  Cloudflare runs it automatically every time something changes on GitHub.
- **`dist/`** is the finished site. It's rebuilt from scratch each time and
  is never uploaded to GitHub.

**Payments** happen on a Jotform order form connected to Square. Each order
emails grandma everything — the customer's details, their ad, their uploaded
image, and the payment.

## Folder guide

| Folder / file | What it is |
|---|---|
| `data/advertisements.json` | Every company listing and ad |
| `data/hotels.json` | Hotels, by state |
| `data/regulations.json` | Pilot car rules, by state |
| `data/adjacency.json` | Which states border which (drives "Nearby" links) |
| `data/states.json` | The list of states and provinces |
| `assets/` | Stylesheet, script, logo, and ad images |
| `build.py` | Builds the site. Python 3, nothing to install. |
| `MIGRATION_MAP.md` | Every old web address and where it now goes |

## Ad rules built into the site

- **Higher-paying ads always appear above lower ones.** Banner → Super →
  Bold → Basic. The `priority` number only orders ads *within* the same
  level, so a typo can never push a basic listing above a banner.
- **An ad with an `endDate` disappears by itself the day after that date.**
  When someone cancels, set the end date — no need to delete anything.
- **`"active": false`** hides an ad without deleting it.
- **Hotels appear inside the state's company table**, in their own city,
  highlighted — right where drivers are already looking.

## Connecting Cloudflare (one time)

1. Sign up at **dash.cloudflare.com** (free).
2. Go to **Workers & Pages → Create → Pages → Connect to Git**, and choose
   this repository.
3. Use these build settings:
   - **Framework preset:** None
   - **Build command:** `python3 build.py`
   - **Build output directory:** `dist`
4. Click **Save and Deploy**. A couple of minutes later you get a preview
   address ending in `.pages.dev`.
5. When you're ready to go live: **Custom domains → Set up a custom domain**
   → `uspilotcars.com`, and follow the DNS steps it shows. That's the
   moment the old site is replaced.

After that, any change pushed to GitHub is live within a few minutes. If an
update ever breaks something, open **Deployments**, pick the last good one,
and choose **Rollback**.

## Checking the site on your own computer (optional)

```bash
python3 build.py
cd dist && python3 -m http.server 8000
```

Then open http://localhost:8000. (The old-address redirects only work once
it's on Cloudflare.)

## Before launch

- [ ] Review the privacy page wording — it should mention Jotform and Square
- [ ] Confirm the four prices shown as a "value" on the Advertise page (Super Listing and Banner packages) -- a value is not a price
- [ ] Turn off GitHub Pages for this repository (Settings → Pages), so
      search engines don't find a second copy of the site
