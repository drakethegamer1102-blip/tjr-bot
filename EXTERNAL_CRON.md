# Reliable scheduling via cron-job.org (free, no credit card)

GitHub's built-in cron is best-effort — it drops and delays runs (it skipped a whole
day's summary and most market-hours scans). cron-job.org fires on time and calls
GitHub's `workflow_dispatch` API to run the bot. No code changes needed.

## 1. Make a scoped token for the timer (safe)
GitHub → Settings → Developer settings → **Fine-grained tokens** → Generate new token
- **Repository access:** Only select repositories → `tjr-bot`
- **Permissions → Repository permissions → Actions: Read and write**
- Generate, copy the token (`github_pat_…`).

This token can ONLY trigger Actions on this one repo — far safer than a broad token.
After this is working you can delete the old classic `ghp_…` token.

## 2. Create a free cron-job.org account
<https://cron-job.org> → sign up (free, no card).
In Settings, set your timezone to **America/New_York** so schedules follow ET and
auto-handle daylight saving (no more UTC math).

## 3. Add 3 cron jobs
Every job uses the same URL + method + headers; only the body and schedule differ.

- **URL:** `https://api.github.com/repos/drakethegamer1102-blip/tjr-bot/actions/workflows/trade.yml/dispatches`
- **Request method:** POST
- **Headers** (under Advanced → Headers):
  ```
  Authorization: Bearer <YOUR_FINE_GRAINED_TOKEN>
  Accept: application/vnd.github+json
  X-GitHub-Api-Version: 2022-11-28
  Content-Type: application/json
  ```

| Job | Request body | Schedule (America/New_York) |
|-----|--------------|------------------------------|
| **Scan** | `{"ref":"main","inputs":{"mode":"once"}}` | every 5 min, Mon–Fri, 09:30–16:00 |
| **Daily summary** | `{"ref":"main","inputs":{"mode":"summary"}}` | 16:05, Mon–Fri |
| **Weekly recap** | `{"ref":"main","inputs":{"mode":"weekly"}}` | 16:10, Fridays |

## 4. Verify
On the Scan job, click **Run now / Test run**. You should get **HTTP 204**, and a run
appears in the repo's **Actions** tab within seconds. That's it — reliable scheduling.

## Note on the old GitHub schedule
The workflow's built-in `schedule:` is left on as a harmless fallback. Once you've
confirmed cron-job.org works, tell Claude to remove it so you never get a rare
duplicate summary.
