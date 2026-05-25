# OpenHome

OpenHome is a black-and-white Minecraft hosting interface by CLT.

This repo now follows the Stitch AI visual direction: sharp monochrome surfaces, technical typography, rigid layout structure, and a serious infrastructure feel instead of a playful gaming theme.

## Product status

### OpenHome Free
- 1 server
- 1024 MB RAM
- 2 GB storage
- 10 players
- Auto-stop enabled
- Plugins allowed
- Custom worlds allowed

### OpenHome Plus
- Official future premium tier
- More servers
- More RAM
- More storage
- Longer uptime
- Backups
- Custom domains
- Priority startup
- Backend/admin controlled only for now

## Plan rules

- User plan is stored in `profiles.plan`.
- Every new user defaults to `free`.
- The backend reads the user plan and enforces limits from there.
- The frontend must not write `plan = 'plus'` directly.
- There is no self-upgrade flow in this milestone.
- There is no Stripe, PayPal, MercadoPago, crypto, or fake checkout flow.
- Clicking Plus-related CTAs should only show: `OpenHome Plus is planned, but not available yet.`
- When payments exist later, only backend, webhook, or admin processes should change `profiles.plan`.

## Stitch integration

The app frontend is being migrated into the Stitch CLT system while preserving working auth and backend actions.

Current Stitch direction in this repo:
- Black, white, and grayscale only
- Inter + Geist feel
- Sharp borders and technical cards
- Minimal premium dashboard layouts
- Separate motion layer in `app/static/css/animations.css` and `app/static/js/openhome-animations.js`
- No fake server data replacing real backend-driven flows

## Pages

The primary interface pages are:
- `app/static/index.html`
- `app/static/login.html`
- `app/static/register.html`
- `app/static/servers.html`
- `app/static/pricing.html`
- `app/static/server-detail.html`
- `app/static/auth-confirm.html`

## Architecture

### Frontend
- Static pages live in `app/static/`
- Main visual system lives in `app/static/css/styles.css`
- Motion layer lives in `app/static/css/animations.css`
- App behavior lives in `app/static/js/app.js`
- Plan metadata for UI messaging lives in `app/static/js/plans.js`

### Backend
- FastAPI entry point: `app/main.py`
- Server APIs: `app/api/servers.py`
- Profile plan API: `app/api/profile.py`
- Supabase service integration: `app/services/auth.py`
- Plan definitions and enforcement: `app/plans.py`
- Supabase schema and RLS: `supabase_schema.sql`

## Deployment note

This repository can be published to GitHub Pages as a static interface preview, but GitHub Pages cannot run:
- FastAPI
- Supabase service-role operations
- payment webhooks
- container orchestration

That means the frontend can be hosted statically, but authenticated server actions still require a deployed backend/API elsewhere.

For GitHub Pages deployments, set the backend origin in `app/static/js/supabase-client.js`:

```js
const OPENHOME_API_BASE = "https://your-backend.example.com";
```

## Roadmap

### Phase 1
- Auth with Supabase
- Free plan defaults and backend-enforced limits
- Server listing and creation flow
- Stitch-based visual migration

### Phase 2
- Server detail hardening
- Better per-server configuration flows
- Cleaner upload and network management UX
- More production-safe API behavior

### Phase 3
- Full deployment split between static frontend and hosted backend
- Plan administration workflow
- More robust resource telemetry and lifecycle control

### Phase 4
- Payments and webhook-based plan activation
- OpenHome Plus operational rollout
- Backups, domains, and priority infrastructure features

## Repo map

```text
OpenHome/
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── services/
│   ├── static/
│   ├── config.py
│   ├── main.py
│   └── plans.py
├── scripts/
├── supabase_schema.sql
├── requirements.txt
└── README.md
```
