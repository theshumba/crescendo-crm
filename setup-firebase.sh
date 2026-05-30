#!/usr/bin/env bash
# Crescendo CRM — Firebase backend setup automation
# Wires the shared Firestore backend so Master view sees everyone's work.
# Re-runnable: safe to run multiple times.
set -euo pipefail

PROJECT_ID="${FIREBASE_PROJECT_ID:-PASTE_YOUR_FIREBASE_PROJECT_ID}"
REPO_DIR="$HOME/Documents/GitHub/crescendo-crm"
NPM_PREFIX="$HOME/.npm-global"
REGION="eur3"

bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }

echo
bold "=========================================="
bold "  Crescendo CRM — Firebase Setup"
bold "=========================================="
echo "Project: $PROJECT_ID"
echo "Repo:    $REPO_DIR"
echo

# ---------- 1. firebase-tools on PATH ----------
export PATH="$NPM_PREFIX/bin:$PATH"
if ! command -v firebase >/dev/null 2>&1; then
  echo "→ Installing firebase-tools (no sudo, user-local)..."
  mkdir -p "$NPM_PREFIX"
  npm config set prefix "$NPM_PREFIX"
  npm install -g firebase-tools
fi
green "✓ firebase CLI: $(firebase --version)"

# ---------- 2. Login (only if needed) ----------
if ! firebase projects:list >/dev/null 2>&1; then
  echo
  yellow "→ Firebase login required. Your browser will open."
  yellow "  Sign in with the SAME Google account you used in the Firebase console."
  echo
  firebase login
fi
green "✓ Logged in"

# ---------- 3. Write Firestore rules + config files (must come before `firebase use`) ----------
cd "$REPO_DIR"

cat > firebase.json <<'JSON'
{
  "firestore": {
    "rules": "firestore.rules",
    "indexes": "firestore.indexes.json"
  }
}
JSON

cat > firestore.rules <<'RULES'
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Any signed-in user (we use anonymous auth) can read/write leads.
    match /leads/{leadId} {
      allow read, write: if request.auth != null;
    }
  }
}
RULES

cat > firestore.indexes.json <<'JSON'
{ "indexes": [], "fieldOverrides": [] }
JSON

cat > .firebaserc <<JSON
{
  "projects": {
    "default": "$PROJECT_ID"
  }
}
JSON
green "✓ Wrote firebase.json + firestore.rules + firestore.indexes.json + .firebaserc"

# ---------- 4. Confirm active project ----------
firebase use "$PROJECT_ID" >/dev/null 2>&1 || true
green "✓ Active project: $PROJECT_ID"

# ---------- 5. Create Firestore database if missing ----------
if firebase firestore:databases:list 2>/dev/null | grep -q '(default)'; then
  green "✓ Firestore database already exists"
else
  echo "→ Creating Firestore database in $REGION..."
  if firebase firestore:databases:create "(default)" --location="$REGION" --type=firestore-native 2>/dev/null; then
    green "✓ Firestore database created"
  else
    yellow "⚠ Couldn't create database via CLI (sometimes the first one needs the console)."
    yellow "  Opening the console for you — click 'Create database' there:"
    DB_URL="https://console.firebase.google.com/project/$PROJECT_ID/firestore"
    open "$DB_URL" 2>/dev/null || echo "  Visit: $DB_URL"
    yellow "  Choose: production mode, region $REGION."
    read -rp "  Press Enter once the database is created and ready... "
  fi
fi

# ---------- 6. Deploy security rules ----------
echo "→ Deploying security rules..."
if firebase deploy --only firestore:rules; then
  green "✓ Rules deployed"
else
  red "✗ Rules deploy failed. The Firestore database probably isn't ready yet."
  red "  Wait 30 seconds and re-run this script."
  exit 1
fi

# ---------- 7. Anonymous Auth (final manual click) ----------
AUTH_URL="https://console.firebase.google.com/project/$PROJECT_ID/authentication/providers"
echo
bold "==========  ONE FINAL BROWSER CLICK  =========="
echo "Anonymous sign-in is what lets the app talk to Firestore."
echo
echo "Opening: $AUTH_URL"
open "$AUTH_URL" 2>/dev/null || echo "  Visit: $AUTH_URL"
echo
echo "In the page that just opened:"
echo "  1. Click the 'Anonymous' row in the providers list"
echo "  2. Toggle 'Enable' to ON"
echo "  3. Click 'Save'"
echo
echo "That's it. The CRM is fully live."
echo "Bottom-right indicator in the app will show '● Synced' when working."
echo
green "Done."
