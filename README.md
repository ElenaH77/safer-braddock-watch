# Safer Braddock Calendar Watcher

Polls https://alexandria.granicus.com/ViewPublisher.php?view_id=57 every 5 minutes. The moment the **05/16/26 City Council Public Hearing** row gains an agenda link (i.e. the agenda is published, which means the speaker signup form will accept May 16), a Pushover emergency alert fires — bypasses Do Not Disturb, retries every 30 seconds for an hour until acknowledged.

## One-time setup

### 1. Pushover

- Sign up at https://pushover.net
- Install the Pushover iOS app (\$5 one-time) — notifications mirror to Apple Watch automatically
- Copy your **User Key** from the dashboard
- Create a new Application at https://pushover.net/apps/build (name it "Safer Braddock Watcher"); copy the **API Token**

### 2. Push this directory to a new public GitHub repo

```bash
cd "Safer Braddock Watch"
git init
git add .
git commit -m "Initial scaffold"
gh repo create safer-braddock-watch --public --source=. --push
```

Why public: GitHub Actions is unlimited on public repos. Private repos have a 2,000-min/month cap that this poller would exceed (5-min cron × 24×7 ≈ 8,640 runs/month). Nothing sensitive lives in the code — Pushover keys go in Secrets.

### 3. Add the secrets

```bash
gh secret set PUSHOVER_USER   # paste your User Key
gh secret set PUSHOVER_TOKEN  # paste your API Token
```

### 4. Test the notification chain end-to-end

```bash
gh workflow run poll.yml -f test_alert=true
```

A high-priority (priority 1) Pushover should land within ~1 minute. If not, open `gh run view --log` to debug.

### 5. Confirm the cron is running

After ~10 minutes:

```bash
gh run list --workflow=poll.yml
```

You should see scheduled runs every ~5 minutes. Note: GitHub Actions cron can lag up to 15 minutes during peak times — known limitation, not fixable from our side.

## What the alerts mean

| Title | Priority | Meaning |
|---|---|---|
| `5/16 AGENDA PUBLISHED — sign up NOW` | 2 (emergency, bypasses DND) | The agenda link just appeared. Send the newsletter blast. |
| `5/16 agenda URL changed` | 0 (low) | URL was re-issued — possible re-publication. Verify but not urgent. |
| `5/16 row missing from Granicus` | 0 | The meeting was removed (cancelled/rescheduled). Manual check. |
| `Safer Braddock watcher: page structure changed` | 0 | Granicus restructured the page. Script needs updating. Fires at most once per day. |
| `Safer Braddock test` | 1 (high) | Manual test fire from `workflow_dispatch`. |

## Turning it off after May 16

```bash
gh workflow disable poll.yml
```

## How it works

`scripts/poll.py` fetches the Granicus page, parses the table with BeautifulSoup, finds the row containing both `05/16/26` and `City Council`, and checks for an `<a href>` inside that row. State is stored in `state/last_seen.json` and committed back by the workflow each run, so the script knows whether the link is *new* this run vs. seen before.

## Known limits

- **Cron drift:** GitHub-side delay can push polls 5–15 min late.
- **Single-source:** if Granicus goes down or restructures, the watcher goes blind. The "page structure changed" alert is the canary.
- **No backup channel:** if Pushover itself is down, you won't be alerted. For a more critical use, add a Twilio SMS fallback in `fire_pushover`.
