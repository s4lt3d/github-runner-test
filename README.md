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
