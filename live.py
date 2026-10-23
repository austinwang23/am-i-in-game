#!/usr/bin/env python3
"""Check for live games via the Riot Spectator API.

Usage:
  python live.py "HalfwayCrooks#KOC"   # is this player in game, and with which pros?
  python live.py --pros                # which pros from players.csv are in game right now?

Options: --platform na1 (server: na1, kr, euw1, ...)  --region americas (account lookups)
"""
import argparse
import csv
import os
import sys
import time
import urllib.parse

import requests

from match_history import QUEUES, get, load_key

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "players.csv")


def champion_names():
    version = requests.get("https://ddragon.leagueoflegends.com/api/versions.json", timeout=15).json()[0]
    data = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json",
                        timeout=15).json()["data"]
    return {int(c["key"]): c["name"] for c in data.values()}


def lookup_puuid(name, tag, key, region):
    account = get(f"https://{region}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
                  f"{urllib.parse.quote(name)}/{urllib.parse.quote(tag)}", key, allow_404=True)
    return account["puuid"] if account else None


def active_game(puuid, key, platform):
    return get(f"https://{platform}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}",
               key, allow_404=True)


def load_rows():
    with open(CSV_PATH, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_rows(rows):
    fields = list(rows[0].keys())
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def ensure_puuids(rows, key, region):
    """Fill in a puuid column for pros that don't have one yet, and save it to the CSV."""
    missing = [r for r in rows if not r.get("puuid")]
    if not missing:
        return
    print(f"Looking up {len(missing)} pro accounts (one-time, saved to players.csv)...", file=sys.stderr)
    for r in rows:
        r.setdefault("puuid", "")
    for i, r in enumerate(missing, 1):
        r["puuid"] = lookup_puuid(r["game_name"], r["tag_line"], key, region) or "NOT_FOUND"
        if r["puuid"] == "NOT_FOUND":
            print(f"  {r['pro']}: {r['riot_id']} not found (renamed?)", file=sys.stderr)
        if i % 20 == 0:
            print(f"  {i}/{len(missing)}", file=sys.stderr)
    save_rows(rows)


def print_game(game, champs, pros_by_puuid, highlight=None):
    queue = QUEUES.get(game.get("gameQueueConfigId"), game.get("gameMode", "?"))
    length = game.get("gameLength", 0)
    elapsed = f"{length // 60}:{length % 60:02d}" if length > 0 else "loading"
    print(f"{queue}  |  in game {elapsed}  |  game id {game['gameId']}")
    for team_id, label in ((100, "Blue"), (200, "Red")):
        print(f"  {label} side")
        for p in game["participants"]:
            if p["teamId"] != team_id:
                continue
            pro = pros_by_puuid.get(p["puuid"])
            tag = f"  <- {pro['pro']} ({pro['team']})" if pro else ""
            marker = "*" if p["puuid"] == highlight else " "
            champ = champs.get(p["championId"], str(p["championId"]))
            print(f"   {marker} {champ:<14}{p.get('riotId', '?'):<30}{tag}")


def check_player(riot_id, key, platform, region):
    if "#" not in riot_id:
        sys.exit("Riot ID must look like Name#TAG")
    name, tag = riot_id.rsplit("#", 1)
    puuid = lookup_puuid(name, tag, key, region)
    if not puuid:
        sys.exit(f"{riot_id} not found on {region}")
    game = active_game(puuid, key, platform)
    if not game:
        print(f"{riot_id} is not in a game on {platform}.")
        return

    rows = load_rows()
    pros_by_puuid = {r["puuid"]: r for r in rows if r.get("puuid") and r["puuid"] != "NOT_FOUND"}
    # Fall back to Riot ID matching for pros whose puuid isn't cached yet.
    pros_by_id = {r["riot_id"].casefold(): r for r in rows}
    for p in game["participants"]:
        pro = pros_by_id.get(p.get("riotId", "").casefold())
        if pro and p["puuid"] not in pros_by_puuid:
            pros_by_puuid[p["puuid"]] = pro

    print_game(game, champion_names(), pros_by_puuid, highlight=puuid)
    found = [pros_by_puuid[p["puuid"]]["pro"] for p in game["participants"]
             if p["puuid"] in pros_by_puuid and p["puuid"] != puuid]
    print(f"\nPros in this game: {', '.join(found) if found else 'none'}")


def check_pros(key, platform, region):
    rows = load_rows()
    ensure_puuids(rows, key, region)
    pros = [r for r in rows if r["puuid"] != "NOT_FOUND"]
    pros_by_puuid = {r["puuid"]: r for r in pros}

    print(f"Checking {len(pros)} pros on {platform}...", file=sys.stderr)
    games = {}
    for i, r in enumerate(pros, 1):
        if any(r["puuid"] in g["puuids"] for g in games.values()):
            continue  # already found in a game we've seen
        game = active_game(r["puuid"], key, platform)
        if game:
            games[game["gameId"]] = {"game": game, "puuids": {p["puuid"] for p in game["participants"]}}
        if i % 20 == 0:
            print(f"  {i}/{len(pros)}", file=sys.stderr)

    if not games:
        print(f"No pros are in a game on {platform} right now.")
        return
    champs = champion_names()
    print(f"\n{len(games)} live game(s) with pros, {time.strftime('%H:%M')}:\n")
    for g in games.values():
        print_game(g["game"], champs, pros_by_puuid)
        print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("riot_id", nargs="?", help='e.g. "HalfwayCrooks#KOC"')
    p.add_argument("--pros", action="store_true", help="check every pro in players.csv")
    p.add_argument("--platform", default="na1", help="game server: na1, kr, euw1, ...")
    p.add_argument("--region", default="americas", help="account region: americas, asia, europe")
    args = p.parse_args()

    key = load_key()
    if args.pros:
        check_pros(key, args.platform, args.region)
    elif args.riot_id:
        check_player(args.riot_id, key, args.platform, args.region)
    else:
        p.error("give a Riot ID or --pros")


if __name__ == "__main__":
    main()
