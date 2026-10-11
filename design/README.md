# Design inputs

Brand and design material for the frontend refactor described in [`specs/18-frontend-redesign.md`](../specs/18-frontend-redesign.md) (the spec reviews each file below and lists the decisions still open). Nothing here is read by the app today.

```
design/
├── project_brief.md     Product/design brief (source of UI ideas, triaged in spec 18 §2.4)
├── brand/
│   ├── palette.md       Stitch design system "Kinetic Horizon": color roles, typography, radii, spacing, components
│   └── logo/
│       ├── logo.png                 Mascot, 1024x1024, white background (master)
│       └── logo_no_background.png   Mascot, 500x500, transparent (used in the UI)
├── stitch/              (optional) full screens exported from Google Stitch
└── references/          (optional) anything else that inspires the design
```

## Status of the inputs

- **Palette, brief, logo: received and reviewed.** `brand/logo/logo_no_background.png` (500×500, transparent) is the logo to use in the UI; `logo.png` (1024×1024, white background) is kept as the high-resolution master.
- **Decisions confirmed:** orange brand (Kinetic Horizon) and a dark theme derived from the palette; the derived values and their contrast checks are in spec 18 §5.1.
- **Optional, whenever you have them:** a vector `brand/logo/logo.svg`, and a flatter icon-only mark for 16-24 px (`brand/logo/icon.svg` or `icon.png`, square and transparent). Without them the favicon is built from the PNG.
- **Needed at implementation time:** your go-ahead to download the Plus Jakarta Sans font files (open-source license), because the UI must work offline.

## Rules

- No personal data and no secrets in these files (the brief and palette contain none today).
- Keep files small (logo under ~1 MB).
- Only files you own or generated yourself; keep any generator terms next to them (`brand/logo/LICENSE.txt`).
- Do not edit `src/jobhunter/web/` from here; ideas go through spec 18 first.

## What happens next

When the frontend refactor is picked up from [`specs/08-roadmap.md`](../specs/08-roadmap.md), the palette becomes the design tokens (with the contrast fixes listed in spec 18), the logo becomes the sidebar badge, hero and favicon, and the brief's ideas are built page by page or turned into their own roadmap tasks.
