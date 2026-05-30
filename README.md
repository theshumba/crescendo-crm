# Crescendo CRM

A self-contained, single-file CRM for managing a lead/outreach pipeline — lead capture and scoring,
a qualification rubric, a Kanban-style pipeline, email/sequence generation, an optional AI assistant,
and a consultant onboarding flow. Everything runs in the browser; no build step.

## Run it

Open `index.html` in a browser, or serve the folder with any static server:

```bash
python3 -m http.server 8000
# then visit http://localhost:8000
```

- **`index.html`** — landing page with links to the CRM and onboarding.
- **`crescendo-crm.html`** — the full CRM dashboard.
- **`onboarding.html`** — consultant onboarding walkthrough.

## Data

By default the CRM stores everything in your browser's **localStorage** (per-browser, per-origin).
It ships with a few **fictional sample leads** so you can see how it works — replace them with your own.
No real contact data is included.

## Optional integrations (bring your own keys)

These are **disabled by default** and use placeholders — plug in your own to enable them:

- **AI assistant (Google Gemini):** add your own key via the chatbot settings panel in the CRM
  (stored in localStorage). No key ships with this repo.
- **Cross-device sync (Firebase):** to sync across devices, paste your own Firebase web config into
  the `window.CRESCENDO_FIREBASE_CONFIG` block near the top of `crescendo-crm.html`. See
  `FIREBASE-SETUP.md`. Until you do, the app stays local-only and never connects anywhere.

## Make it yours

It's a single HTML file — fork it, rebrand it (search/replace the Crescendo name, contact details,
and colours), and adapt the qualification rubric to your own pipeline.
