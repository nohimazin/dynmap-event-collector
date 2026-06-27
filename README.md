<p align="center"><a href="./README_JP.md">日本語</a></p>


# Dynmap / LiveAtlas Public Event Collector

A lightweight, configurable, dependency-free Python 3.9 or newer (uses modern type hints) tool to poll and save public Dynmap or LiveAtlas event logs (chat messages, player join/quit updates) into structured JSONL and CSV formats. 

This collector reads the public JSON endpoints queried by the live map interface. It does not perform authentication, bypass access controls, or require special server-side permissions.

---

## Features

- 🔗 **Plugin Event Support**: Detects events where `source` is `"plugin"`, maps `source` to `discord`, and extracts player names from fields like `author_name`, `author.username`, `displayName`, etc.
- 📁 **Auto-Creation of Configuration**: Generates a default `config.json` configuration template at startup if none is found.
- 📡 **CLI Override Hierarchy**: Easily override any settings in your configuration file using command-line arguments (CLI overrides config file, which overrides generic defaults).
- 📍 **Live Coordinate & Status Tracking**: Caches the latest public player information and supplements events with coordinates, health, and armor values.
- 🔌 **Join/Quit Inference**: Optionally tracks differences in the online player list to infer player join/quit events when the plugin doesn't broadcast native updates.
- 🖥️ **Verbose Output**: Formats and logs collected events to `sys.stderr` in real-time.
- 🎯 **Player Name Extraction**: Attempts to obtain the player name from multiple fields (`player`, `playerName`, `account`, `author_name`, `author.username`, `displayName`, etc.) to support various source formats.
- 📸 **Snapshot Handling**: When `--snapshot` is enabled, the initial player list and the full update JSON payload are saved as a snapshot event to the JSONL output (CSV is not used).
- 🛑 **Graceful Shutdown**: Pressing **Ctrl+C** stops the script. The state file is updated after each successful poll, so on the next start the collector resumes from the last saved position.
- 🔄 **Automatic Retry**: Network and JSON parsing errors are automatically retried with exponential backoff for robustness.

---

## Quick Start

1. **Run the script for the first time**:
   ```bash
   python dynmap_collector.py
   ```
   At first startup, the script will notice `config.json` is missing and auto-create a default template:
   ```text
   Created a default configuration file template at config.json
   ```
   **If the `base` URL is not set in the generated configuration, the script will exit with an error message**:
   ```text
   Error: --base URL must be specified either in the config file or as a command line argument.
   ```

2. **Configure your target Dynmap/LiveAtlas Server**:
   Open the generated `config.json` and set the `"base"` URL of your target server (e.g. `https://dynmap.example.com` or a custom proxy base).
   
   Alternatively, specify it directly via the CLI:
   ```bash
   python dynmap_collector.py --base https://dynmap.example.com --verbose --duration 10
   ```

**Note:** After the initial `config.json` is created, if the `base` URL is not set, the script will exit with an error. Please set `base` and rerun.
---

## Configuration (`config.json`)

The default configuration file looks like this:
```json
{
  "base": null,
  "world": null,
  "interval": null,
  "duration": 0.0,
  "timeout": 15.0,
  "jsonl_output": "outputs/dynmap_events.jsonl",
  "csv_output": "outputs/dynmap_events.csv",
  "state_file": "outputs/dynmap_state.json",
  "snapshot": false,
  "infer_player_events": false,
  "verbose": false,
  "user_agent": "dynmap-public-collector/1.0"
}
```

### Key Reference
* `base` (string): The base URL of the Dynmap/LiveAtlas public updater.
* `world` (string): The target world name (e.g. `world`, `world_nether`). Defaults to the server's configured default world if `null`.
## CLI Usage

```text
usage: dynmap_collector.py [-h] [--config CONFIG] [--base BASE]
                                    [--world WORLD] [--since SINCE]
                                    [--interval INTERVAL]
                                    [--duration DURATION] [--timeout TIMEOUT]
                                    [--jsonl-output JSONL_OUTPUT]
                                    [--csv-output CSV_OUTPUT]
                                    [--state-file STATE_FILE] [--snapshot]
                                    [--infer-player-events] [--verbose]
                                    [--user-agent USER_AGENT]
```

### CLI Overriding Example:
If you want to run the script using configurations defined in `config.json` but override the polling interval and enable verbose logs:
```bash
python dynmap_collector.py --interval 2.5 --verbose
```

---

## Output Formats

### CSV Headers
```csv
collected_at,event_time,timestamp,type,source,player,message,world,x,y,z,health,armor
```
### JSONL Schema
Every record written to the JSONL file has a similar flat structure; the original un-normalized JSON payload is stored in the `raw` field.
