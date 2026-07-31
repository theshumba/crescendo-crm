#!/usr/bin/env node
// Full read-only backup of the live Firestore `leads` collection.
//
// Uses the same public web config and anonymous auth the CRM itself uses, so it needs no
// service-account key and nothing to set up. Writes a timestamped JSON file into
// _local/backups/ (gitignored, never leaves this machine) and prunes to the newest 30.
//
// Run by hand:      node scripts/backup-leads.mjs
// Runs itself:      ~/Library/LaunchAgents/com.crescendo.crm-backup.plist (daily)
// Restore path:     _local/cleanup_dupes.py reads these same files.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const OUT_DIR = path.join(ROOT, '_local', 'backups');
const KEEP = 30;

// Read the config out of the app file rather than duplicating it, so a project change can
// never leave the backup silently pointing at the wrong database.
const html = fs.readFileSync(path.join(ROOT, 'crescendo-crm.html'), 'utf8');
const apiKey = (html.match(/apiKey:\s*"([^"]+)"/) || [])[1];
const projectId = (html.match(/projectId:\s*"([^"]+)"/) || [])[1];
if (!apiKey || !projectId || apiKey.startsWith('PASTE') || projectId.startsWith('PASTE')) {
  console.error('No real Firebase config found in crescendo-crm.html. Nothing backed up.');
  process.exit(1);
}

const authRes = await fetch(`https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=${apiKey}`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ returnSecureToken: true })
});
const auth = await authRes.json();
if (!auth.idToken) { console.error('Anonymous sign-in failed:', auth.error || auth); process.exit(1); }

// Firestore REST paginates; walk every page or the backup is quietly partial.
const documents = [];
let pageToken = '';
do {
  const url = `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents/leads`
    + `?pageSize=300${pageToken ? '&pageToken=' + encodeURIComponent(pageToken) : ''}`;
  const r = await fetch(url, { headers: { Authorization: 'Bearer ' + auth.idToken } });
  const j = await r.json();
  if (j.error) { console.error('Read failed:', j.error); process.exit(1); }
  (j.documents || []).forEach(d => documents.push(d));
  pageToken = j.nextPageToken || '';
} while (pageToken);

// Refuse to write a backup that looks like a wipe. A backup file is only worth having if you
// can trust it, and overwriting good history with an empty read is how backups betray you.
const live = documents.filter(d => !d.fields?._deleted?.booleanValue);
const existing = fs.existsSync(OUT_DIR)
  ? fs.readdirSync(OUT_DIR).filter(f => f.startsWith('leads-') && f.endsWith('.json')).sort()
  : [];
if (live.length === 0) { console.error('Read back zero live leads. Refusing to write a backup.'); process.exit(1); }
if (existing.length) {
  const prev = JSON.parse(fs.readFileSync(path.join(OUT_DIR, existing[existing.length - 1]), 'utf8'));
  const prevLive = (prev.leads || []).length;
  if (prevLive > 20 && live.length < prevLive * 0.5) {
    console.error(`Read ${live.length} leads but the last backup had ${prevLive}. Refusing to write; check the database first.`);
    process.exit(1);
  }
}

fs.mkdirSync(OUT_DIR, { recursive: true });
const now = new Date();
const p2 = n => String(n).padStart(2, '0');
const stamp = `${now.getFullYear()}${p2(now.getMonth() + 1)}${p2(now.getDate())}-${p2(now.getHours())}${p2(now.getMinutes())}${p2(now.getSeconds())}`;
const file = path.join(OUT_DIR, `leads-${stamp}.json`);
fs.writeFileSync(file, JSON.stringify({
  takenAt: now.toISOString(),
  projectId,
  counts: { documents: documents.length, live: live.length, tombstones: documents.length - live.length },
  leads: documents
}, null, 0));

// Prune oldest, keeping the newest KEEP files.
const all = fs.readdirSync(OUT_DIR).filter(f => f.startsWith('leads-') && f.endsWith('.json')).sort();
all.slice(0, Math.max(0, all.length - KEEP)).forEach(f => fs.unlinkSync(path.join(OUT_DIR, f)));

console.log(`${live.length} live leads (${documents.length - live.length} tombstones) backed up to ${path.relative(ROOT, file)}`);
console.log(`${Math.min(all.length, KEEP)} backups kept.`);
