# Setting Up Your Training Dashboard

Your coach has built you a personal training dashboard that pulls your Garmin data automatically and shows it on a private website only you (and your coach) can see.

Setup takes about 10 minutes. You'll need a GitHub account — it's free.

---

## What you'll end up with

- A live dashboard at `https://YOUR-NAME.github.io/YOUR-NAME-marathon-dashboard/`
- Automatically refreshes every 6 hours from your Garmin
- Your coach can see your readiness, weekly load, and session data in their Coach Hub
- **Your Garmin password never leaves GitHub's encrypted secret storage — your coach cannot see it**

---

## Step 1 — Create a free GitHub account

Go to [github.com](https://github.com) and sign up if you don't have an account.  
Pick a username (e.g. `janesmith`) — this becomes part of your dashboard URL.

---

## Step 2 — Create your repo from the template

1. Open this link (your coach will send you the exact URL):  
   `https://github.com/Seanhelmot/sean-marathon-dashboard`

2. Click the green **"Use this template"** button → **"Create a new repository"**

3. Fill in:
   - **Owner**: your GitHub username
   - **Repository name**: `firstname-lastname-marathon-dashboard` (e.g. `jane-smith-marathon-dashboard`)
   - **Visibility**: Public *(required for the free GitHub Pages hosting)*

4. Click **"Create repository"**

---

## Step 3 — Add your Garmin credentials as secrets

This is how the dashboard logs into Garmin to pull your data. GitHub stores these encrypted — nobody can read them back out, including your coach.

1. In your new repo, go to **Settings** (top menu) → **Secrets and variables** → **Actions**

2. Click **"New repository secret"** and add:

   | Name | Value |
   |------|-------|
   | `GARMIN_EMAIL` | Your Garmin Connect email address |
   | `GARMIN_PASSWORD` | Your Garmin Connect password |

3. Click **"Add secret"** after each one

---

## Step 4 — Enable GitHub Pages

This publishes your dashboard as a website.

1. Still in **Settings**, click **Pages** in the left sidebar

2. Under **Source**, select:
   - Branch: `main`
   - Folder: `/ (root)`

3. Click **Save**

Your dashboard URL will appear at the top of the page:  
`https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPO-NAME/`

---

## Step 5 — Run the first data pull

1. Go to the **Actions** tab in your repo

2. Click **"Refresh Garmin Data"** in the left sidebar

3. Click **"Run workflow"** → **"Run workflow"**

4. Wait about 60 seconds, then refresh your dashboard URL

---

## Step 6 — Send your coach your URL

Once your dashboard is loading, send your coach:
- Your dashboard URL: `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/`

That's all they need. They'll add you to the Coach Hub and can see your readiness and training data from there.

---

## After setup

- **Data refreshes automatically** every 6 hours (you don't need to do anything)
- **To trigger a manual refresh** after a run: Actions tab → Refresh Garmin Data → Run workflow
- **To update your training plan**: your coach edits `data/plan.json` directly in your repo
- **Password changed?** Update the `GARMIN_PASSWORD` secret in Settings → Secrets

---

## Troubleshooting

**Dashboard shows "loading" but nothing appears**  
→ The Actions workflow may have failed. Check the Actions tab for a red ✗ — click it to see the error log and send it to your coach.

**Garmin login failing in the workflow**  
→ Double-check the `GARMIN_EMAIL` and `GARMIN_PASSWORD` secrets are spelled correctly (no extra spaces). Re-add them if needed.

**Pages shows a 404**  
→ GitHub Pages can take 5–10 minutes to go live the first time. Wait and refresh.

---

*Questions? Contact your coach.*
