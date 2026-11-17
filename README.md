# github-runner-test

A demo of a GitHub Actions **self-hosted runner** on a Mac. Every push to `main`
runs [`scripts/increment.sh`](scripts/increment.sh) on this machine, which bumps
the counter below and commits it back with `[skip ci]` so it doesn't retrigger itself.

## Runner stats

<!-- runner-stats:start -->
- Run count: **2**
- Last ran: **2026-11-17 04:57:44 UTC**
- Triggered by commit: `5405d29`
<!-- runner-stats:end -->

## How it works

1. You push a commit to `main`.
2. [`.github/workflows/on-main.yml`](.github/workflows/on-main.yml) queues a job for `runs-on: self-hosted`.
3. The runner on the Mac picks it up, checks out the repo, and runs the script.
4. The workflow commits the updated README as `github-actions[bot]` with `[skip ci]`
   in the message. GitHub skips workflows for that commit, so there is no loop.

## Setting up the runner

1. On GitHub: **Settings → Actions → Runners → New self-hosted runner → macOS**.
2. Run the download and `./config.sh --url ... --token ...` commands it shows, in a
   folder outside this repo (e.g. `~/actions-runner`).
3. Start it: `./run.sh` (foreground) or `./svc.sh install && ./svc.sh start` (background service).
4. The runner should show as **Idle** on the Runners page.

Then trigger it with:

```bash
git commit --allow-empty -m "trigger runner" && git push
```

## Network config backup demo (`netdemo/`)

Simulates backing up switch configs on every change ticket and on a schedule.

- `netdemo/netdemo.py`: simulated switch fleet (lives in `~/netdemo-sim`), a
  fetcher standing in for Oxidized, and the ticket/report/audit tools.
- `netdemo/commit_changes.sh`: commits only real changes, one commit per device,
  attributed to the user who made it. Files where only the lines matching
  `netdemo/ignore-patterns.txt` changed (timestamps) are discarded.
- `netdemo-sweep.yml`: full backup every 15 minutes, plus an audit of changes
  not covered by any ticket.
- `netdemo-ticket.yml`: on ticket start it sweeps and tags `CR-123-pre`; on
  ticket end it sweeps, tags `CR-123-post`, and writes `netdemo/reports/CR-123.md`.

Try it:

```bash
netdemo/netdemo.py init --count 200
gh workflow run netdemo-ticket.yml -f action=start -f ticket=CR-1 -f assignee=jsmith
netdemo/netdemo.py change --user jsmith --count 3
netdemo/netdemo.py change --user mlopez --device sw-access-020
gh workflow run netdemo-ticket.yml -f action=end -f ticket=CR-1
```

From Jira Automation, send a web request instead of `gh workflow run`:

```
POST https://api.github.com/repos/OWNER/REPO/dispatches
{"event_type": "cr-start", "client_payload": {"ticket": "CR-1", "assignee": "jsmith"}}
{"event_type": "cr-end",   "client_payload": {"ticket": "CR-1"}}
```
