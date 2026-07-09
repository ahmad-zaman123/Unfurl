# Unfurl

[![CI](https://github.com/ahmad-zaman123/Unfurl/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmad-zaman123/Unfurl/actions/workflows/ci.yml)

**Social preview images as an API.** Generate the `og:image` card for any link with a
single call — dynamic titles, themes, and logos, signed and cached, ready to drop into a
meta tag.

<!-- After deploying, fill these in:
**🔗 Live demo: [unfurl-…vercel.app](https://…)**

> **Try it** — sign in with **`demo@unfurl.app`** / **`demo1234`**.
-->

A **Django REST** backend (`Backend/`) and a **React + Vite** dashboard (`Frontend/`) in one
repo. The interesting part isn't the image — it's the platform around it: hashed API keys,
HMAC-signed URLs, per-key rate limiting, plan quotas, usage analytics, and an SSRF-guarded
image fetcher. Deploys to Vercel with Neon Postgres and Upstash Redis.

## What it does

You authenticate to **mint** a card, and get back a **signed public URL**:

```
POST /api/v1/cards   (Authorization: Bearer sk_live_…)   →  { "url": ".../api/v1/og?…&sig=…" }
```

That URL is what goes in `<meta property="og:image">`. It needs no auth (crawlers can't send
a token), it's tamper-proof (signed), and it's cached after the first render.

## Why this project

Most "OG image generator" demos stop at drawing text. Unfurl is built around the problems a
real image API has to solve — each implemented deliberately and covered by the flow.

### 1. The create/serve split — because `og:image` is a bare URL

A crawler fetching `<meta property="og:image" content="…">` does a plain GET with **no
headers**. So an authenticated "return a PNG" endpoint can't actually be used in a meta tag.
Unfurl separates **create** (authenticated, mints a URL) from **serve** (public, cacheable),
which is the only model that works in practice.

### 2. HMAC-signed URLs that double as the cache key

The served URL carries an HMAC signature over its parameters. The public endpoint **rejects
any unsigned or tampered request** (change one character of the title → `403`). Because the
signature is a deterministic hash of the params, it's also a perfect **content-cache key** —
identical cards render once, then serve from cache (`X-Cache: HIT`).

### 3. API keys done like Stripe

Keys are stored as a **SHA-256 hash** with only a display prefix (`sk_live_ab12…`); the raw
key is shown exactly once. A custom DRF authentication class handles `Authorization: Bearer
sk_…` and cleanly coexists with the dashboard's JWT auth on the same header.

### 4. Per-key rate limiting + plan quotas

A fixed-window limiter (atomic cache `incr`, Redis in prod) enforces per-minute and per-day
limits per key, returning standard `X-RateLimit-*` and `Retry-After` headers. A per-account
**monthly quota** is enforced by plan (Free/Pro). Only API-key traffic is metered — dashboard
previews stay unlimited.

### 5. SSRF-guarded logo fetching

The `logo` parameter fetches a remote image. The fetcher resolves the host and **rejects any
non-public IP** (loopback, private ranges, and `169.254.x` cloud-metadata), allows only
`http(s)`, **refuses redirects**, and caps size and time. Fetch failures are fail-safe — the
card just renders without the logo.

## Tech stack

**Backend:** Python 3.11 · Django 4.2 · Django REST Framework · Pillow · JWT (`simplejwt`) ·
OpenAPI/Swagger (`drf-spectacular`)

**Frontend:** React 19 · Vite · React Router

**Deploy:** Vercel (serverless Python + static React) · Neon Postgres · Upstash Redis

## API

Interactive Swagger docs at `/api/docs/`, and a quickstart at `/docs` in the app.

## Local setup

Runs on SQLite and local-memory cache out of the box — no Postgres or Redis needed for dev.

### Backend

```bash
cd Backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver 8010
```

### Frontend

```bash
cd Frontend
npm install
cp .env.example .env          # VITE_API_URL points at the backend (default: localhost:8010)
npm run dev                   # http://localhost:5175
```
