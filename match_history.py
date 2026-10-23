#!/usr/bin/env python3
"""Print recent match history for a Riot ID.

Setup (once): python3 -m venv .venv && .venv/bin/pip install requests
Usage: .venv/bin/python match_history.py "HalfwayCrooks#KOC" [--count 20] [--queue 420] [--region americas]

The API key is read from $RIOT_API_KEY, or from a .riot_key file next to this script.
"""
import argparse
import csv
import datetime
import os
import sys
import time
import urllib.parse

import requests

QUEUES = {
    400: "Draft", 420: "Ranked Solo", 430: "Blind", 440: "Ranked Flex",
    450: "ARAM", 490: "Quickplay", 1700: "Arena", 1900: "URF",
}


def load_key():
    key = os.environ.get("RIOT_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".riot_key")
    if os.path.exists(path):
        with open(path) as f:
            return f.read().strip()
    sys.exit("No API key: set RIOT_API_KEY or put the key in .riot_key next to this script.")


def load_pros():
    """Map lowercased Riot ID -> CSV row, from players.csv next to this script."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players.csv")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {row["riot_id"].casefold(): row for row in csv.DictReader(f)}


def get(url, key, params=None, allow_404=False):
    while True:
        resp = requests.get(url, headers={"X-Riot-Token": key}, params=params, timeout=15)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", "5"))
            print(f"  rate limited, waiting {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code == 404 and allow_404:
            return None
        if not resp.ok:
            sys.exit(f"HTTP {resp.status_code} for {resp.url}\n{resp.text}")
        return resp.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("riot_id", help='e.g. "HalfwayCrooks#KOC"')
    p.add_argument("--count", type=int, default=20)
    p.add_argument("--queue", type=int, help="queue id filter, e.g. 420 for ranked solo")
    p.add_argument("--region", default="americas", help="americas | europe | asia | sea")
    args = p.parse_args()

    if "#" not in args.riot_id:
        sys.exit("Riot ID must look like Name#TAG")
    name, tag = args.riot_id.rsplit("#", 1)
    key = load_key()
    base = f"https://{args.region}.api.riotgames.com"

    account = get(f"{base}/riot/account/v1/accounts/by-riot-id/"
                  f"{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}", key)
    puuid = account["puuid"]
    print(f"{account['gameName']}#{account['tagLine']}  puuid={puuid}\n")

    params = {"start": 0, "count": args.count}
    if args.queue:
        params["queue"] = args.queue
    ids = get(f"{base}/lol/match/v5/matches/by-puuid/{puuid}/ids", key, params)
    if not ids:
        print("No matches found.")
        return

    pros = load_pros()
    seen = {}  # riot_id -> (pro row, [teammate/opponent per game])

    print(f"{'Date':<17}{'Queue':<13}{'Result':<7}{'Champion':<14}{'Role':<9}"
          f"{'K/D/A':<10}{'CS':>4}{'Dmg':>8}{'Len':>7}")
    wins = 0
    for match_id in ids:
        info = get(f"{base}/lol/match/v5/matches/{match_id}", key)["info"]
        me = next(x for x in info["participants"] if x["puuid"] == puuid)
        found = []
        for p in info["participants"]:
            if p["puuid"] == puuid:
                continue
            rid = f"{p.get('riotIdGameName', '')}#{p.get('riotIdTagline', '')}"
            pro = pros.get(rid.casefold())
            if pro:
                side = "ally" if p["teamId"] == me["teamId"] else "enemy"
                found.append(f"{pro['pro']} ({pro['team']}, {side}, {p['championName']})")
                seen.setdefault(pro["riot_id"], (pro, []))[1].append(side)
        wins += me["win"]
        date = datetime.datetime.fromtimestamp(info["gameStartTimestamp"] / 1000)
        queue = QUEUES.get(info["queueId"], str(info["queueId"]))
        kda = f"{me['kills']}/{me['deaths']}/{me['assists']}"
        cs = me["totalMinionsKilled"] + me["neutralMinionsKilled"]
        mins, secs = divmod(info["gameDuration"], 60)
        print(f"{date:%Y-%m-%d %H:%M}  {queue:<13}{'Win' if me['win'] else 'Loss':<7}"
              f"{me['championName']:<14}{me.get('teamPosition') or '-':<9}{kda:<10}"
              f"{cs:>4}{me['totalDamageDealtToChampions']:>8}{mins:>4}:{secs:02d}")
        if found:
            print(f"    pros: {', '.join(found)}")
    print(f"\n{wins}W {len(ids) - wins}L over {len(ids)} games")

    if seen:
        print("\nPros played with/against:")
        for pro, sides in sorted(seen.values(), key=lambda v: -len(v[1])):
            print(f"  {pro['pro']:<12}{pro['team']:<6}{pro['riot_id']:<28}"
                  f"{len(sides)} games ({sides.count('ally')} ally, {sides.count('enemy')} enemy)")
    else:
        print("\nNo pros from players.csv in these games.")


if __name__ == "__main__":
    main()
