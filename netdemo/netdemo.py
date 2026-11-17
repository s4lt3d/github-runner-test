#!/usr/bin/env python3
"""Network config backup demo.

A simulated switch fleet stands in for real devices, and `fetch` stands in for
Oxidized's file output. `report` and `audit` read the git history that
commit_changes.sh builds.

Simulated devices live in $NETDEMO_HOME (default ~/netdemo-sim), outside the
repo, the way real switches would.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import random
import re
import subprocess
import sys

HOME = pathlib.Path(os.environ.get("NETDEMO_HOME", pathlib.Path.home() / "netdemo-sim"))
DEVICES = HOME / "devices"
REPO = pathlib.Path(__file__).resolve().parent
TICKETS = REPO / "tickets"
USERS = ["jsmith", "akumar", "mlopez", "tchen", "rpatel"]
CHANGE_RE = re.compile(r"^(\S+) changed by (\S+)")


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def cisco_time(t):
    return t.strftime("%H:%M:%S UTC %a %b %d %Y")


def load(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


# ---------- simulated fleet ----------

def cmd_init(a):
    DEVICES.mkdir(parents=True, exist_ok=True)
    rng = random.Random(42)
    t = cisco_time(utcnow())
    for i in range(1, a.count + 1):
        role = "core" if i <= max(2, a.count // 50) else "access"
        name = f"sw-{role}-{i:03d}"
        ports = {
            f"GigabitEthernet1/0/{p}": {
                "description": rng.choice(["user-port", "printer", "ap-uplink", "voip"]),
                "vlan": rng.choice([10, 20, 30]),
                "shutdown": False,
            }
            for p in range(1, 9)
        }
        save(DEVICES / f"{name}.json", {
            "hostname": name,
            "vlans": {"10": "users", "20": "voice", "30": "printers"},
            "ports": ports,
            "ntp": "10.0.0.1",
            "last_change": {"time": t, "user": "provisioning"},
            "nvram": t,
        })
    print(f"Created {a.count} simulated devices in {DEVICES}")


def device_files():
    files = sorted(DEVICES.glob("*.json"))
    if not files:
        sys.exit(f"No simulated devices in {DEVICES}. Run: netdemo.py init")
    return files


def mutate(dev, rng):
    port = rng.choice(sorted(dev["ports"]))
    p = dev["ports"][port]
    kind = rng.choice(["vlan", "description", "shutdown", "new-vlan"])
    if kind == "vlan":
        p["vlan"] = rng.choice([v for v in map(int, dev["vlans"]) if v != p["vlan"]] or [10])
        return f"{port} moved to vlan {p['vlan']}"
    if kind == "description":
        p["description"] = rng.choice(["camera", "kiosk", "conf-room", "lab"])
        return f"{port} description -> {p['description']}"
    if kind == "shutdown":
        p["shutdown"] = not p["shutdown"]
        return f"{port} {'shut' if p['shutdown'] else 'no shut'}"
    vid = str(rng.randint(100, 999))
    dev["vlans"][vid] = f"project-{vid}"
    return f"added vlan {vid}"


def cmd_change(a):
    rng = random.Random()
    files = device_files()
    if a.device:
        targets = [DEVICES / f"{d}.json" for d in a.device]
        for t in targets:
            if not t.exists():
                sys.exit(f"Unknown device {t.stem}")
    else:
        targets = rng.sample(files, min(a.count, len(files)))
    t = cisco_time(utcnow())
    for path in targets:
        dev = load(path)
        what = mutate(dev, rng)
        dev["last_change"] = {"time": t, "user": a.user}
        dev["nvram"] = t
        save(path, dev)
        print(f"{dev['hostname']}: {what} (by {a.user})")


def render(dev, fetched):
    out = [
        f"! Fetched: {cisco_time(fetched)}",
        f"! Last configuration change at {dev['last_change']['time']} by {dev['last_change']['user']}",
        f"! NVRAM config last updated at {dev['nvram']}",
        f"hostname {dev['hostname']}",
        "!",
    ]
    for vid in sorted(dev["vlans"], key=int):
        out += [f"vlan {vid}", f" name {dev['vlans'][vid]}", "!"]
    for port in sorted(dev["ports"], key=lambda s: int(s.rsplit("/", 1)[1])):
        p = dev["ports"][port]
        out += [f"interface {port}", f" description {p['description']}",
                f" switchport access vlan {p['vlan']}"]
        if p["shutdown"]:
            out.append(" shutdown")
        out.append("!")
    out += [f"ntp server {dev['ntp']}", "end", ""]
    return "\n".join(out)


def cmd_fetch(a):
    """Stand-in for Oxidized: dump every device's running config to a folder."""
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random()
    now = utcnow()
    files = device_files()
    for path in files:
        dev = load(path)
        # Noise: someone ran "write memory" with no real change.
        if rng.random() < 0.05:
            dev["nvram"] = cisco_time(now)
            save(path, dev)
        (out / f"{dev['hostname']}.cfg").write_text(render(dev, now))
    print(f"Fetched {len(files)} configs into {out}")


# ---------- reporting from git history ----------

def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout


def change_commits(rev_range=None):
    args = ["log", "--reverse", "--format=%h%x09%cI%x09%s"]
    if rev_range:
        args.append(rev_range)
    args += ["--", "backups"]
    rows = []
    for line in git(*args).splitlines():
        sha, when, subject = line.split("\t", 2)
        m = CHANGE_RE.match(subject)
        if m:
            rows.append({"sha": sha, "time": dt.datetime.fromisoformat(when).astimezone(dt.timezone.utc),
                         "device": m.group(1), "user": m.group(2)})
    return rows


def load_tickets():
    tickets = []
    for path in sorted(TICKETS.glob("*.json")):
        t = load(path)
        t["start"] = dt.datetime.fromisoformat(t["started"])
        t["end"] = dt.datetime.fromisoformat(t["ended"]) if t.get("ended") else None
        tickets.append(t)
    return tickets


def cmd_ticket(a):
    TICKETS.mkdir(exist_ok=True)
    path = TICKETS / f"{a.ticket}.json"
    now = utcnow().isoformat(timespec="seconds")
    if a.action == "start":
        if not a.assignee:
            sys.exit("--assignee is required to start a ticket")
        save(path, {"ticket": a.ticket, "assignee": a.assignee, "started": now, "ended": None})
    else:
        if not path.exists():
            sys.exit(f"{a.ticket} was never started")
        t = load(path)
        t["ended"] = now
        save(path, t)
    print(f"{a.ticket} {a.action} at {now}")


def cmd_report(a):
    t = load(TICKETS / f"{a.ticket}.json")
    end = a.to or f"{a.ticket}-post"
    rows = change_commits(f"{a.ticket}-pre..{end}")
    mine = [r for r in rows if r["user"] == t["assignee"]]
    other = [r for r in rows if r["user"] != t["assignee"]]
    lines = [f"# {a.ticket} change report", "",
             f"- Assignee: **{t['assignee']}**",
             f"- Window: {t['started']} to {t['ended']}",
             f"- Devices changed: **{len({r['device'] for r in rows})}**", ""]

    def table(title, items):
        lines.extend([f"## {title} ({len(items)})", ""])
        if not items:
            lines.extend(["None.", ""])
            return
        lines.extend(["| Device | Changed by | Detected | Commit |", "|---|---|---|---|"])
        for r in items:
            lines.append(f"| {r['device']} | {r['user']} | {r['time']:%Y-%m-%d %H:%M}Z | `{r['sha']}` |")
        lines.append("")

    table("Changed by the assignee", mine)
    table("Changed by someone else during the window (review)", other)
    lines += ["## Diff", "", "```diff",
              git("diff", f"{a.ticket}-pre", end, "--", "backups").rstrip(),
              "```", ""]
    print("\n".join(lines))


def cmd_audit(a):
    tickets = load_tickets()
    now = utcnow()
    unexplained = []
    for r in change_commits():
        if r["user"] == "provisioning":
            continue
        covered = any(t["assignee"] == r["user"] and t["start"] <= r["time"] <= (t["end"] or now)
                      for t in tickets)
        if not covered:
            unexplained.append(r)
    print("# Unexplained config changes\n")
    if not unexplained:
        print("None. Every change matches an open ticket for the user who made it.")
        return
    print("These changes were made outside any ticket assigned to the person who made them.\n")
    print("| Device | Changed by | Detected | Commit |\n|---|---|---|---|")
    for r in unexplained:
        print(f"| {r['device']} | {r['user']} | {r['time']:%Y-%m-%d %H:%M}Z | `{r['sha']}` |")
    if a.fail:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create the simulated fleet")
    p.add_argument("--count", type=int, default=200)
    p.set_defaults(fn=cmd_init)
    p = sub.add_parser("change", help="simulate an engineer changing devices")
    p.add_argument("--user", required=True, help=f"who made the change, e.g. {', '.join(USERS)}")
    p.add_argument("--count", type=int, default=1, help="number of random devices")
    p.add_argument("--device", nargs="+", help="specific device names instead of random ones")
    p.set_defaults(fn=cmd_change)
    p = sub.add_parser("fetch", help="dump all configs (Oxidized stand-in)")
    p.add_argument("--out", default=str(REPO / "backups"))
    p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("ticket", help="record a ticket start or end")
    p.add_argument("action", choices=["start", "end"])
    p.add_argument("ticket")
    p.add_argument("--assignee")
    p.set_defaults(fn=cmd_ticket)
    p = sub.add_parser("report", help="markdown report for a closed ticket")
    p.add_argument("ticket")
    p.add_argument("--to", help="end of range (default: TICKET-post tag)")
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser("audit", help="list changes not covered by any ticket")
    p.add_argument("--fail", action="store_true", help="exit 1 if any are found")
    p.set_defaults(fn=cmd_audit)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
