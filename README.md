# discord-incremental-backup
A script which uses [Tyrrrz/DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) to make incremental backups of Discord channel categories, including threads and forum posts to be viewed in [slatinsky/DiscordChatExporter-frontend](https://github.com/slatinsky/DiscordChatExporter-frontend).

Tested on Linux only.

**Note:**
Automating user accounts violates Discord TOS. Use at your own risk.


## Prerequisites
- Python 3.11+.
- A Discord user token with access to channels you want to export ([guide](https://github.com/Tyrrrz/DiscordChatExporter/blob/master/.docs/Token-and-IDs.md)).


## Usage (Linux)

```bash
git clone https://github.com/queze1/discord-incremental-backup.git
cd discord-incremental-backup/

# set up venv (ignore if not using venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# find the latest version for your platform from https://github.com/Tyrrrz/DiscordChatExporter/releases
wget https://github.com/Tyrrrz/DiscordChatExporter/releases/download/2.46/DiscordChatExporter.Cli.linux-x64.zip
unzip DiscordChatExporter.Cli.linux-x64.zip -d dce/
chmod +x dce/DiscordChatExporter.Cli

# copy sample config and edit it
cp config.example.json config.json
nano config.json

# run the script
python3 main.py
```

### `config.json` example

```json
{
  "token": "YOUR_DISCORD_USER_TOKEN_HERE",
  "categories": [
    "123456789012345678"
  ],
  "excluded_channels": [],
  "threads": []
}
```


## How It Works
1. Find channels from `channel_ids.txt`, skipping inaccessible or invalid channels.
2. Find Discord channels, threads and forum posts according to `config.json`.
3. Save successfully found channels to `channel_ids.txt`.
4. Incrementally export each channel into `/output`:
    1. If a pre-existing export does not exist, or if only one partition exists (channels are split every 1000 messages by default), overwrite the previous export.
    2. If more than one partition exists:
        - Delete the latest (incomplete) partition.
        - Export into `/output_temp`, starting from the last message of the second-last partition.
        - Move the new partitions into `/output` and rename them.
        - Normalise paths so they point to `/output/media`.
        - E.g. A channel has 5000 messages, 2500 of which are backed up into 3 partitions. The 3rd partition (containing 500 messages) is deleted, and the export begins from the 2001st message. 3 new partitions are created into `/output_temp`. Then, they are moved into `/output` and renamed to parts 3-5.

## Differences with [slatinsky/DiscordChatExporter-incrementalBackup](https://github.com/slatinsky/DiscordChatExporter-incrementalBackup)
1. Intended for personal use.
2. Only supports one Discord token.
3. Backs up channel categories, not servers.
4. Allows excluding Discord channels from backup.
5. Uses [dolfies/discord.py-self](https://github.com/dolfies/discord.py-self) to find archived threads and forum posts instead of DCE (faster).
6. Requires manual input for active threads/forum posts (limitation from [dolfies/discord.py-self](https://github.com/dolfies/discord.py-self)).
7. Doesn't require installing [slatinsky/DiscordChatExporter-frontend](https://github.com/slatinsky/DiscordChatExporter-frontend).

## Known Issues
- Images not displaying on [Tyrrrz/DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter), even when the relative path is correct.
