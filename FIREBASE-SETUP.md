# Firebase setup — 5 minutes, one-time

Crescendo CRM now syncs across every device through Firebase. Until you paste your project's config into `crescendo-crm.html`, the app runs in local-only mode (the old behaviour). Do this **once** and everyone's work becomes visible on the Master view.

---

## What you're doing

Creating a free Google Firebase project. It gives you:
- A shared Firestore database every logged-in user writes into
- Free tier: 50,000 reads/day, 20,000 writes/day (way more than we need)
- No credit card, no server to run

---

## Step 1 — Create the project

1. Go to **https://console.firebase.google.com/** (sign in with your Google account).
2. Click **Add project** (or **Create a project**).
3. Name it `crescendo-crm` (or anything). Click **Continue**.
4. **Disable Google Analytics** (optional toggle near the bottom — we don't need it). Click **Create project**.
5. Wait ~30 seconds, click **Continue**.

## Step 2 — Add a web app to the project

1. On the project home, click the **</>** (web) icon — "Add an app to get started".
2. App nickname: `Crescendo CRM`. **Don't** tick "Firebase Hosting". Click **Register app**.
3. Firebase shows a code block that looks like this:

   ```js
   const firebaseConfig = {
     apiKey: "AIzaSy...",
     authDomain: "crescendo-crm-xxxxx.firebaseapp.com",
     projectId: "crescendo-crm-xxxxx",
     storageBucket: "crescendo-crm-xxxxx.appspot.com",
     messagingSenderId: "123456789",
     appId: "1:123456789:web:abcdef"
   };
   ```

4. **Copy those six values.** You'll paste them in Step 5. Click **Continue to console**.

## Step 3 — Turn on Firestore (the database)

1. Left sidebar → **Build → Firestore Database**.
2. Click **Create database**.
3. Choose **Start in production mode**. Click **Next**.
4. Region: pick **eur3 (europe-west)** (you're in the UK). Click **Enable**.
5. Wait ~30 seconds. You now have a Firestore database.

## Step 4 — Turn on Anonymous Authentication

Firestore rules need users to be "signed in", so we use anonymous sign-in (transparent, no login prompt).

1. Left sidebar → **Build → Authentication**.
2. Click **Get started**.
3. On the **Sign-in method** tab, find **Anonymous**, click it, toggle **Enable**, click **Save**.

## Step 5 — Paste the config into Crescendo CRM

1. Open `crescendo-crm.html` in a text editor.
2. Near the top (around line 18), find this block:

   ```js
   window.CRESCENDO_FIREBASE_CONFIG = {
     apiKey: "PASTE_APIKEY",
     authDomain: "PASTE.firebaseapp.com",
     projectId: "PASTE",
     ...
   };
   ```

3. Replace each `PASTE...` value with the matching value from Step 2.4.
4. Save the file.

## Step 6 — Set Firestore security rules

This allows any signed-in user to read/write leads. Since sign-in is anonymous and automatic, this is effectively the team.

1. Firebase Console → **Firestore Database → Rules** tab.
2. Replace the rules with this:

   ```
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /leads/{leadId} {
         allow read, write: if request.auth != null;
       }
     }
   }
   ```

3. Click **Publish**.

## Step 7 — Deploy and test

1. Commit + push the HTML change:
   ```
   git add crescendo-crm.html
   git commit -m "Wire up Firebase config"
   git push
   ```
2. GitHub Pages will redeploy in ~30 seconds.
3. Open the CRM in two different browsers (or have Ameer refresh on his device).
4. Make a change on one browser. Watch it appear on the other within a second.
5. Log in as **Master** — you now see everybody's leads and activity feed.

A small **● Synced** indicator appears bottom-right when the shared backend is live.
If it shows **● Offline (local only)**, the config isn't valid — double-check Step 5.

---

## Troubleshooting

**"● Sync error: permission-denied"** — You skipped Step 6. Set the security rules.

**"● Sync error: unauthenticated"** — You skipped Step 4. Enable Anonymous auth.

**Still shows "● Offline (local only)" after config pasted** — You have placeholder values like `PASTE_APIKEY` still in the config. Open browser devtools → Console, look for `[CrescendoSync]` messages.

**Ameer's data didn't migrate** — His browser's local data needs to get into the cloud. Have him open the app after the Firebase update is live; the app auto-pushes local leads into Firestore on first connect. If it doesn't, he can export CSV (button in app) and re-import on the master account.

---

## Cost

Firebase Spark (free) plan covers this use case indefinitely at current team size:
- **50,000 reads/day** — you'd need 50 users each viewing 1,000 leads/day to hit it
- **20,000 writes/day** — you'd need ~200 lead edits per person per day to hit it
- **1 GiB storage** — the entire leads JSON is <5 MB

You'll never see a bill.
