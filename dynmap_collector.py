from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
TARGET_TZ = timezone.utc
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


EVENT_TYPES = {
    "chat",
    "webchat",
    "playerjoin",
    "playerquit",
}

CSV_FIELDS = [
    "collected_at",
    "event_time",
    "timestamp",
    "type",
    "source",
    "player",
    "message",
    "world",
    "x",
    "y",
    "z",
    "health",
    "armor",
]


def fetch_json(url: str, timeout: float = 15.0, user_agent: str = "dynmap-public-collector/1.0") -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset))


def now_iso() -> str:
    return datetime.now(TARGET_TZ).isoformat()


def timestamp_to_iso(timestamp: Any) -> str:
    if timestamp is None:
        return ""
    try:
        value = float(timestamp)
    except (TypeError, ValueError):
        return ""
    if value > 10_000_000_000:
        value /= 1000.0
    return datetime.fromtimestamp(value, timezone.utc).astimezone(TARGET_TZ).isoformat()


def normalize_event(
    raw: dict[str, Any],
    source: str = "dynmap-update",
    player_coords_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize a raw event dict into the unified CSV/JSONL schema.

    The ``source`` field is overridden when the raw payload indicates it came
    from a Discord plugin (``raw.get('source') == 'plugin'``). In that case the
    source is set to ``'discord'`` so downstream processing can distinguish the
    two origins.
    """
    collected_at = now_iso()
    # Extract player name from various possible fields, handling Discord author structures
    player = (
        raw.get("playerName")
        or raw.get("player")
        or raw.get("account")
        or raw.get("username")
        or raw.get("name")
        or raw.get("displayName")
        or raw.get("author_name")
        or (raw.get("author") if isinstance(raw.get("author"), str) else None)
        or (raw.get("author", {}) or {}).get("username")
        or (raw.get("author", {}) or {}).get("name")
        or (raw.get("author", {}) or {}).get("displayName")
    )
    # Fallback: extract name from Discord channel string like "[Discord | Moderator] karaha69"
    if not player:
        channel = raw.get("channel")
        if isinstance(channel, str):
            # Split on closing bracket and trim
            parts = channel.split("]")
            if len(parts) > 1:
                candidate = parts[1].strip()
                if candidate:
                    player = candidate
            else:
                # Fallback to last word
                tokens = channel.strip().split()
                if tokens:
                    player = tokens[-1]
    
    
    
    world = raw.get("world")
    x = raw.get("x")
    y = raw.get("y")
    z = raw.get("z")
    health = raw.get("health")
    armor = raw.get("armor")
    
    if player and player_coords_cache and player in player_coords_cache:
        coords = player_coords_cache[player]
        if world is None:
            world = coords.get("world")
        if x is None:
            x = coords.get("x")
        if y is None:
            y = coords.get("y")
        if z is None:
            z = coords.get("z")
        if health is None:
            health = coords.get("health")
        if armor is None:
            armor = coords.get("armor")

    # Distinguish Discord messages (raw source == 'plugin')
    if raw.get("source") == "plugin":
        source = "discord"
    
    return {
        "collected_at": collected_at,
        "event_time": timestamp_to_iso(raw.get("timestamp")),
        "source": source,
        "type": raw.get("type"),
        "timestamp": raw.get("timestamp"),
        "player": player,
        "message": raw.get("message"),
        "world": world,
        "x": x,
        "y": y,
        "z": z,
        "health": health,
        "armor": armor,
        "raw": raw,
    }


def player_names(payload: dict[str, Any]) -> set[str]:
    names = set()
    for player in payload.get("players", []):
        name = player.get("account") or player.get("name")
        if name:
            names.add(str(name))
    return names


def write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, record: dict[str, Any]) -> None:
    ensure_csv(path)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writerow({field: record.get(field, "") for field in CSV_FIELDS})


def ensure_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    if not write_header:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()


def write_event(args: argparse.Namespace, record: dict[str, Any]) -> None:
    write_jsonl(args.jsonl_output, record)
    write_csv(args.csv_output, record)
    if args.verbose:
        player = record.get("player") or "-"
        message = record.get("message") or ""
        x = record.get("x")
        y = record.get("y")
        z = record.get("z")
        health = record.get("health")
        armor = record.get("armor")

        if x is not None and y is not None and z is not None and x != "" and y != "" and z != "":
            try:
                pos_str = f" pos=({int(round(float(x)))},{int(round(float(y)))},{int(round(float(z)))})"
            except (ValueError, TypeError):
                pos_str = f" pos=({x},{y},{z})"
        else:
            pos_str = ""

        hp_str = ""
        if health is not None and health != "":
            try:
                h_val = float(health)
                if h_val.is_integer():
                    hp_str = f" hp={int(h_val)}"
                else:
                    hp_str = f" hp={h_val:.1f}"
            except (ValueError, TypeError):
                hp_str = f" hp={health}"

        armor_str = ""
        if armor is not None and armor != "":
            try:
                a_val = float(armor)
                if a_val.is_integer():
                    armor_str = f" armor={int(a_val)}"
                else:
                    armor_str = f" armor={a_val}"
            except (ValueError, TypeError):
                armor_str = f" armor={armor}"

        source_str = f" source={record.get('source')}" if record.get('source') else ""
        print(f"{record.get('type')}{source_str} player={player}{pos_str}{hp_str}{armor_str} message={message}", file=sys.stderr)


def read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"state read failed ({path}): {exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def write_state(path: Path, base: str, world: str, timestamp: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "base": base,
        "world": world,
        "timestamp": timestamp,
        "saved_at": now_iso(),
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def state_timestamp(args: argparse.Namespace, base: str, world: str) -> int:
    if args.since is not None:
        return int(args.since)
    state = read_state(args.state_file)
    if state.get("base") == base and state.get("world") == world:
        try:
            return int(state.get("timestamp", 0))
        except (TypeError, ValueError):
            return 0
    return 0


def infer_player_event(
    event_type: str,
    name: str,
    timestamp: int,
    player_coords_cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    world = ""
    x = ""
    y = ""
    z = ""
    health = ""
    armor = ""

    if player_coords_cache and name in player_coords_cache:
        coords = player_coords_cache[name]
        world = coords.get("world", "")
        if world is None:
            world = ""
        x = coords.get("x", "")
        if x is None:
            x = ""
        y = coords.get("y", "")
        if y is None:
            y = ""
        z = coords.get("z", "")
        if z is None:
            z = ""
        health = coords.get("health", "")
        if health is None:
            health = ""
        armor = coords.get("armor", "")
        if armor is None:
            armor = ""

    return {
        "collected_at": now_iso(),
        "event_time": timestamp_to_iso(timestamp),
        "source": "player-list-diff",
        "type": event_type,
        "timestamp": timestamp,
        "player": name,
        "message": "",
        "world": world,
        "x": x,
        "y": y,
        "z": z,
        "health": health,
        "armor": armor,
    }


def should_stop(deadline: float | None) -> bool:
    return deadline is not None and time.monotonic() >= deadline


def fetch_json_retry(
    url: str,
    args: argparse.Namespace,
    deadline: float | None,
    label: str,
    interval: float = 1.0,
) -> dict[str, Any] | None:
    failures = 0
    while True:
        if should_stop(deadline):
            return None
        try:
            return fetch_json(url, timeout=args.timeout, user_agent=args.user_agent)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            failures += 1
            backoff = min(interval * (failures + 1), 30.0)
            print(f"{label} failed: {exc}", file=sys.stderr)
            time.sleep(backoff)


def collect(args: argparse.Namespace) -> int:
    base = args.base.rstrip("/")
    deadline = time.monotonic() + args.duration if args.duration else None
    ensure_csv(args.csv_output)

    config = fetch_json_retry(f"{base}/up/configuration", args, deadline, "configuration fetch")
    if config is None:
        return 0

    world = args.world or config.get("defaultworld") or "world"
    interval = args.interval or max(float(config.get("updaterate", 1000.0)) / 1000.0, 1.0)

    print(
        f"base={base} world={world} interval={interval:.1f}s "
        f"chat_enabled={config.get('allowchat')} webchat_enabled={config.get('allowwebchat')}",
        file=sys.stderr,
    )

    timestamp = state_timestamp(args, base, world)
    initial_payload = fetch_json_retry(
        f"{base}/up/world/{world}/{timestamp}",
        args,
        deadline,
        "initial update fetch",
        interval,
    )
    if initial_payload is None:
        return 0

    player_coords_cache: dict[str, dict[str, Any]] = {}

    def update_coords_cache(p_payload: dict[str, Any]) -> None:
        for p in p_payload.get("players", []):
            name = p.get("account") or p.get("name")
            if name:
                player_coords_cache[str(name)] = {
                    "world": p.get("world"),
                    "x": p.get("x"),
                    "y": p.get("y"),
                    "z": p.get("z"),
                    "health": p.get("health"),
                    "armor": p.get("armor"),
                }
        if len(player_coords_cache) > 10000:
            curr_names = player_names(p_payload)
            for name in list(player_coords_cache.keys()):
                if name not in curr_names:
                    player_coords_cache.pop(name, None)

    update_coords_cache(initial_payload)

    timestamp = int(initial_payload.get("timestamp", timestamp))
    previous_players = player_names(initial_payload)
    write_state(args.state_file, base, world, timestamp)

    if args.snapshot:
        write_jsonl(
            args.jsonl_output,
            {
                "collected_at": now_iso(),
                "source": "initial-snapshot",
                "type": "players",
                "timestamp": timestamp,
                "players": sorted(previous_players),
                "raw": initial_payload,
            },
        )

    consecutive_failures = 0
    while True:
        if should_stop(deadline):
            write_state(args.state_file, base, world, timestamp)
            return 0

        time.sleep(interval)
        try:
            payload = fetch_json(f"{base}/up/world/{world}/{timestamp}", timeout=args.timeout, user_agent=args.user_agent)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            consecutive_failures += 1
            backoff = min(interval * (consecutive_failures + 1), 30.0)
            print(f"poll failed: {exc}", file=sys.stderr)
            time.sleep(backoff)
            continue

        consecutive_failures = 0
        timestamp = int(payload.get("timestamp", timestamp))
        write_state(args.state_file, base, world, timestamp)

        update_coords_cache(payload)

        joined_players_this_tick = set()
        quit_players_this_tick = set()

        for update in payload.get("updates", []):
            if update.get("type") in EVENT_TYPES:
                record = normalize_event(update, player_coords_cache=player_coords_cache)
                write_event(args, record)
                u_type = record.get("type")
                u_player = record.get("player")
                if u_player:
                    if u_type == "playerjoin":
                        joined_players_this_tick.add(u_player)
                    elif u_type == "playerquit":
                        quit_players_this_tick.add(u_player)

        current_players = player_names(payload)
        if args.infer_player_events:
            for name in sorted((current_players - previous_players) - joined_players_this_tick):
                write_event(args, infer_player_event("playerjoin_inferred", name, timestamp, player_coords_cache=player_coords_cache))
            for name in sorted((previous_players - current_players) - quit_players_this_tick):
                write_event(args, infer_player_event("playerquit_inferred", name, timestamp, player_coords_cache=player_coords_cache))
        previous_players = current_players


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        default_config = {
            "base": None,
            "world": None,
            "interval": None,
            "duration": 0.0,
            "timeout": 15.0,
            "jsonl_output": "outputs/dynmap_events.jsonl",
            "csv_output": "outputs/dynmap_events.csv",
            "state_file": "outputs/dynmap_state.json",
            "snapshot": False,
            "infer_player_events": False,
            "verbose": False,
            "user_agent": "dynmap-public-collector/1.0",
            "timezone_offset": 0,
        }
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with config_path.open("w", encoding="utf-8") as handle:
                json.dump(default_config, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            print(f"Created a default configuration file template at {config_path}", file=sys.stderr)
            return default_config
        except Exception as exc:
            print(f"Warning: Failed to create default config at {config_path}: {exc}", file=sys.stderr)
            return {}
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except Exception as exc:
        print(f"Warning: Failed to load config from {config_path}: {exc}", file=sys.stderr)
    return {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None, help="Path to config JSON file")
    parser.add_argument("--base", default=None, help="Dynmap/LiveAtlas base URL")
    parser.add_argument("--world", default=None, help="Dynmap world name; defaults to configuration.defaultworld")
    parser.add_argument(
        "--since",
        type=int,
        default=None,
        help="Dynmap update timestamp to start from; overrides --state-file",
    )
    parser.add_argument("--interval", type=float, default=None, help="Polling interval in seconds")
    parser.add_argument("--duration", type=float, default=None, help="Stop after N seconds; 0 means run forever")
    parser.add_argument("--timeout", type=float, default=None, help="HTTP timeout in seconds")
    parser.add_argument(
        "--jsonl-output",
        type=Path,
        default=None,
        help="JSONL output path",
    )
    parser.add_argument("--csv-output", type=Path, default=None, help="CSV output path")
    parser.add_argument("--state-file", type=Path, default=None, help="Poll state JSON path")
    parser.add_argument("--snapshot", action="store_true", default=None, help="Write initial player/update snapshot")
    parser.add_argument(
        "--infer-player-events",
        action="store_true",
        default=None,
        help="Infer joins/quits from changes in the public player list",
    )
    parser.add_argument("--verbose", action="store_true", default=None, help="Print collected events to stderr")
    parser.add_argument("--user-agent", default=None, help="HTTP User-Agent header")
    parser.add_argument("--timezone-offset", type=int, default=None, help="Hours offset from UTC for timestamps")

    args = parser.parse_args()

    # Determine config file path
    script_dir = Path(__file__).resolve().parent
    config_path = Path(args.config) if args.config else script_dir / "config.json"

    config = load_config(config_path)

    # Generic defaults in case they are not in config or CLI
    defaults = {
        "base": None,
        "world": None,
        "since": None,
        "interval": None,
        "duration": 0.0,
        "timeout": 15.0,
        "jsonl_output": Path("outputs/dynmap_events.jsonl"),
        "csv_output": Path("outputs/dynmap_events.csv"),
        "state_file": Path("outputs/dynmap_state.json"),
        "snapshot": False,
        "infer_player_events": False,
        "verbose": False,
        "user_agent": "dynmap-public-collector/1.0",
        "timezone_offset": 0,
    }

    resolved = argparse.Namespace()
    resolved.config = config_path

    path_keys = {"jsonl_output", "csv_output", "state_file"}

    for key, val in defaults.items():
        cli_val = getattr(args, key, None)
        if cli_val is not None:
            setattr(resolved, key, cli_val)
        elif key in config:
            config_val = config[key]
            # Convert string paths to Path objects if necessary
            if key in path_keys and config_val is not None:
                config_val = Path(config_val)
            setattr(resolved, key, config_val)
        else:
            setattr(resolved, key, val)

    # Validate that base URL is specified
    if not resolved.base:
        parser.print_usage(sys.stderr)
        print("Error: --base URL must be specified either in the config file or as a command line argument.", file=sys.stderr)
        sys.exit(1)

    global TARGET_TZ
    TARGET_TZ = timezone(timedelta(hours=resolved.timezone_offset or 0))
    return resolved


if __name__ == "__main__":
    parsed_args = parse_args()
    try:
        raise SystemExit(collect(parsed_args))
    except KeyboardInterrupt:
        print("interrupted; latest state has been saved", file=sys.stderr)
        raise SystemExit(130)
