# PLUTO vProctor — Zoho Catalyst Deployment Guide

> Audience: Project owner — no Catalyst expertise required  
> Updated: 2026-11-17  
> Platform: Zoho Catalyst (India data center, Sandbox tier)  
> Project ID: 73453000000046001

---

> [!IMPORTANT]
> This guide deploys a **development/demo staging** environment.  
> It does **not** deploy a production SaaS. See Cost Control guide before proceeding.

---

## Before You Start — Prerequisites

You will need:

- [ ] Zoho account with Catalyst access (the same account that has the \$250 credit — verify its type first)
- [ ] Catalyst CLI installed: run `npm install -g @zohocloud/catalyst-cli` in a terminal
- [ ] Node.js installed (required for the CLI)
- [ ] Python 3.12 on your machine (already confirmed available)
- [ ] The PLUTO repository on your machine at `D:\_TY\MDM\PLUTO-vProctor`

---

## Part 1 — Build the Frontend

The frontend is a React app. You need to build it into static files before uploading.

**1.1 — Set up the production environment file**

```
cd D:\_TY\MDM\PLUTO-vProctor\frontend
copy .env.production.example .env.production
```

Open `.env.production` in Notepad. You will fill in the AppSail URL in Step 2 (after deploying the backend). For now, leave the placeholder — you can rebuild after.

**1.2 — Build the frontend**

```
cd D:\_TY\MDM\PLUTO-vProctor\frontend
npm install
npm run build
```

This creates the `frontend/dist/` folder with all static files. Build takes about 30 seconds.

---

## Part 2 — Deploy the Backend (AppSail)

AppSail is Zoho's platform for running server-side code (like a web server).

**2.1 — Authenticate the Catalyst CLI**

```
catalyst login
```

Follow the browser prompt. Sign in with your Zoho account.

**2.2 — Link to your Catalyst project**

```
cd D:\_TY\MDM\PLUTO-vProctor
catalyst project switch
```

Select your project from the list (ID: 73453000000046001).

**2.3 — Set the required environment variable — SECRET_KEY**

> [!CAUTION]
> You MUST set a real secret key. Never deploy without one.

Generate a secret key:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output. Then in the **Catalyst Console** (browser):

1. Go to **AppSail → pluto-backend → Environment Variables**
2. Add a new variable: **Name** = `SECRET_KEY`, **Value** = the key you generated
3. Save

**2.4 — Set the CORS origin (you can update this later)**

In the same Environment Variables section, add:

- **Name** = `CORS_ORIGINS`, **Value** = `["https://YOUR_PROJECT.catalyst.zohocloud.com"]`

You will find the actual Web Client Hosting URL after Step 3. Update this after.

**2.5 — Deploy the backend**

```
cd D:\_TY\MDM\PLUTO-vProctor
catalyst appsail deploy
```

This uploads the backend code, installs Python dependencies, and starts the server.  
Wait for the CLI to show: **"Service deployed successfully"**

**2.6 — Note the AppSail service URL**

In the Catalyst Console → AppSail → pluto-backend, copy the **Service URL**. It looks like:

```
https://pluto-backend-73453000000046001.catalyst.zohocloud.com
```

You will need this URL in Part 3.

---

## Part 3 — Deploy the Frontend (Web Client Hosting)

Web Client Hosting serves the static HTML/CSS/JS files from `frontend/dist/`.

**3.1 — Update the frontend API URL**

Open `frontend/.env.production` in Notepad. Change the line:

```
VITE_API_BASE_URL=https://YOUR_APPSAIL_URL.catalyst.zohocloud.com
```

Replace the placeholder with the AppSail Service URL you noted in Step 2.6.

**3.2 — Rebuild the frontend with the real URL**

```
cd D:\_TY\MDM\PLUTO-vProctor\frontend
npm run build
```

**3.3 — Deploy the frontend**

```
cd D:\_TY\MDM\PLUTO-vProctor
catalyst webclient deploy
```

The CLI will upload `frontend/dist/`. Wait for confirmation.

**3.4 — Note the frontend URL**

The CLI will show a URL like:

```
https://73453000000046001.catalyst.zohocloud.com
```

This is the URL you share with others to access PLUTO.

---

## Part 4 — Smoke Test (Verify It Works)

**4.1 — Check the backend health**

Open in your browser:

```
https://YOUR_APPSAIL_URL.catalyst.zohocloud.com/health
```

You should see: `{"status": "ok", ...}`

If you get a 503 error, the backend is still starting. Wait 15 seconds and try again.

**4.2 — Run the smoke test script**

```
set PLUTO_BASE_URL=https://YOUR_APPSAIL_URL.catalyst.zohocloud.com
python scripts/smoke_test.py
```

All checks should show ✓ (green checkmarks).

**4.3 — Open the frontend**

Navigate to the frontend URL in your browser. You should see the PLUTO vProctor landing page.

Try:
- Logging in with your admin account
- Creating a new interview session
- Checking the question bank loads

---

## Part 5 — Update the Deployment

When you make code changes and want to redeploy:

```
# If backend changed:
catalyst appsail deploy

# If frontend changed:
cd frontend
npm run build
cd ..
catalyst webclient deploy
```

---

## Part 6 — Stop Resources (Save Credits)

When you are done with a demo session, the backend will auto-scale to zero after ~5 minutes of inactivity. This is automatic.

To manually trigger scale-down or disable the service temporarily:

1. Go to **Catalyst Console → AppSail → pluto-backend**
2. Click **Disable** (this stops all instances and costs zero)
3. Click **Enable** when you need it again

The frontend (Web Client Hosting) is static and costs essentially nothing — leave it running.

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| `/health` returns 503 immediately after deploy | AppSail still starting | Wait 15–30 seconds, retry |
| Login fails with "Invalid token" | SECRET_KEY mismatch | Verify SECRET_KEY env var is set in AppSail console |
| Frontend shows blank page | VITE_API_BASE_URL wrong | Rebuild frontend with correct AppSail URL |
| "CORS error" in browser console | CORS_ORIGINS not set | Set CORS_ORIGINS env var in AppSail to match your frontend domain |
| AI questions not generating | Ollama not available on AppSail | Expected — algorithmic question selection is used instead |
| Session data lost after restart | SQLite ephemerality | Expected for demo. Data is not persisted across AppSail scale-down. |
| `catalyst appsail deploy` fails: Python stack | python_3_12 not available | Change `catalyst.json` → `"stack": "python_3_10"` and retry |
