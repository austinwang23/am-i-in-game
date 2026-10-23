# am-i-in-game

Small Python scripts that use the [Riot Games API](https://developer.riotgames.com) to:

- show a player's recent League of Legends match history, and point out any **Worlds 2026 pros** they played with or against
- check whether a player is **in a live game right now**, and which pros are in it
- check which **pros are in a live game right now**

The pro list (`players.csv`) comes from the [dpm.lol Worlds 2026 SoloQ leaderboard](https://dpm.lol/leaderboards/worlds). It has 95 accounts for pros who qualified for Worlds 2026, each mapped to its Riot ID.

## Setup

You need Python 3 and a Riot API key.

```bash
git clone https://github.com/austinwang23/am-i-in-game.git
cd am-i-in-game
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**API key:** get one at [developer.riotgames.com](https://developer.riotgames.com). Then do one of the following:

```bash
echo "RGAPI-..." > .riot_key          # saved in the project folder (git-ignored)
# or
export RIOT_API_KEY="RGAPI-..."       # for the current terminal session only
```

> Development keys expire every 24 hours. If you start getting `401` or `403` errors, generate a new key.

Activate the venv once per terminal session, then use `python` as normal:

```bash
source .venv/bin/activate
```

## Match history

```bash
python match_history.py "HalfwayCrooks#KOC"
python match_history.py "HalfwayCrooks#KOC" --count 100 --queue 420
```

| Option | Default | Meaning |
|---|---|---|
| `--count` | 20 | Number of recent games (max 100) |
| `--queue` | all | Queue filter, e.g. `420` ranked solo, `440` flex, `450` ARAM |
| `--region` | `americas` | `americas`, `europe`, `asia`, `sea` |

Example output:

```
Date             Queue        Result Champion      Role     K/D/A       CS     Dmg    Len
2026-10-22 21:14  Ranked Solo  Win    Ahri          MIDDLE   8/2/11     231   28410  31:05
    pros: CoreJJ (TLAW, ally, Nautilus), Faker (T1, enemy, Azir)
...
12W 8L over 20 games

Pros played with/against:
  CoreJJ      TLAW  From Iron#1123              3 games (2 ally, 1 enemy)
```

## Live games

```bash
python live.py "HalfwayCrooks#KOC"   # is this player in a game? with which pros?
python live.py --pros                # which pros are in a game right now?
```

| Option | Default | Meaning |
|---|---|---|
| `--platform` | `na1` | Game server: `na1`, `kr`, `euw1`, ... |
| `--region` | `americas` | Account lookup region |

The live check uses the Spectator API. It shows players, champions and sides, but not in-game stats (kills, gold and CS only appear in match history after the game ends). A game only shows up when you check the server it's being played on.

`--pros` checks every account in `players.csv`. The first run looks up each pro's PUUID and saves it to the `puuid` column. After that, each run takes about 95 requests, roughly 2 minutes on a development key.

## players.csv

| Column | Example |
|---|---|
| `rank` | Position on the dpm.lol leaderboard |
| `pro` | `CoreJJ` |
| `team` | `TLAW` |
| `game_name` / `tag_line` | `From Iron` / `1123` |
| `riot_id` | `From Iron#1123` |
| `puuid` | Filled in by `live.py --pros` |

Some pros appear more than once because they have several accounts. If a pro renames an account, update `game_name`, `tag_line` and `riot_id`, then clear that row's `puuid` so it gets looked up again. Rows marked `NOT_FOUND` are skipped.

PUUIDs returned to a development key only work with that key. If lookups start failing with a different key, clear the `puuid` column and run `live.py --pros` again to refill it.

## Rate limits

Development keys are limited to 20 requests per second and 100 requests per 2 minutes. Both scripts wait and retry automatically when they hit the limit, so large runs are slower but still finish.
