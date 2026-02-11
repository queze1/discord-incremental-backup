import asyncio
import json
import os
import pathlib
import re
import shutil
import time
from datetime import timedelta

import discord

from discovery import discover_channels, update_channels_ids

DCE_PATH = "dce/DiscordChatExporter.Cli"

CONFIG_PATH = "config.json"
OUTPUT_PATH = "output"
MEDIA_OUTPUT_PATH = "output/media"
TEMP_DIR = "output_temp"

# 1k messages
PARTITION_LENGTH = "1000"
CHANNEL_EXPORT_OPTIONS = [
    "--fuck-russia",
    "--media",
    "--reuse-media",
    "--media-dir",
    MEDIA_OUTPUT_PATH,
    "--markdown",
    "False",
    "--format",
    "Json",
    "--partition",
    PARTITION_LENGTH,
]


def parse_dce_filename(filename, channel_id):
    """
    Parses a filename to see if it belongs to the given channel_id.

    Returns:
        (base_name, part_number): if match found.
        (None, None): if no match.

    Note: part_number defaults to 1 if the file has no [part N] tag.
    """
    # Explanation:
    # ^(.*\[{channel_id}\])  -> Group 1: Base name. Matches everything up to and including [12345]
    # (?: \[part (\d+)\])?   -> Group 2: Optional part number. Matches " [part 5]"
    # .*                     -> Anything else
    # \.json$                -> Must end with .json
    pattern = re.compile(rf"^(.*\[{channel_id}\])(?: \[part (\d+)\])?.*\.json$")
    match = pattern.match(filename)

    if not match:
        return None, None

    base_name = match.group(1)
    part_str = match.group(2)

    # If "part" is missing, it is implicitly part 1
    part_num = int(part_str) if part_str else 1

    return base_name, part_num


def normalize_json_paths(file_path, media_folder_name="media"):
    """
    Reads a JSON file and replaces absolute paths containing the media folder
    with a relative path.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        def walk_and_fix(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    obj[key] = walk_and_fix(value)
            elif isinstance(obj, list):
                return [walk_and_fix(item) for item in obj]
            elif isinstance(obj, str):
                search_str = f"{media_folder_name}/"
                if search_str in obj:
                    idx = obj.find(search_str)
                    return obj[idx:]
            return obj

        fixed_data = walk_and_fix(data)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(fixed_data, f, indent=2)

    except Exception as e:
        print(f"Error normalising paths in {file_path}: {e}")


def get_last_archived_message_id(channel_id, output_dir: str):
    """
    Finds the last message ID in the existing archive for a channel.
    """
    files: list[tuple] = []
    output_path = pathlib.Path(output_dir)

    if not output_path.exists():
        return None

    for file in output_path.iterdir():
        _, part_n = parse_dce_filename(file.name, channel_id)
        if part_n is not None:
            files.append((file, part_n))

    if not files:
        return None

    # Sort by partition number and pick the last one
    files.sort(key=lambda x: x[1])
    last_file = files[-1][0]

    try:
        with open(last_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "messages" in data and len(data["messages"]) > 0:
                return data["messages"][-1]["id"]
    except Exception:
        pass

    return None


def get_resume_point(channel_id, output_dir: str):
    files: list[tuple] = []
    output_path = pathlib.Path(output_dir)

    if not output_path.exists():
        return None, [], None

    for file in output_path.iterdir():
        _, part_n = parse_dce_filename(file.name, channel_id)

        if part_n is None:
            continue

        files.append((file, part_n))

    files.sort(key=lambda x: x[1])

    if len(files) < 2:
        return None, [], None

    anchor_file = files[-2][0]
    tail_file = files[-1][0]
    files_to_delete = [tail_file]

    last_msg_id = None
    try:
        with open(anchor_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "messages" in data and len(data["messages"]) > 0:
                last_msg = data["messages"][-1]
                last_msg_id = last_msg["id"]
    except Exception as e:
        print(f"Error reading anchor file {anchor_file}: {e}")
        return None, [], None

    next_part_index = files[-1][1]

    return last_msg_id, files_to_delete, next_part_index


def process_temp_files(channel_id, temp_dir, output_dir, start_index):
    temp_path = pathlib.Path(temp_dir)
    output_path = pathlib.Path(output_dir)

    if not temp_path.exists():
        return 0

    found_files = []

    for file in temp_path.iterdir():
        base_name, part_n = parse_dce_filename(file.name, channel_id)

        if base_name:
            found_files.append((file, base_name, part_n))

    # Sort files by part id
    found_files.sort(key=lambda x: x[2])

    current_index = start_index
    files_moved = 0

    for file_obj, base_name, _ in found_files:
        # Construct new name: BaseName + [part N].json
        new_name = f"{base_name} [part {current_index}].json"
        dest_path = output_path.joinpath(new_name)

        print(f"Moving temp file: '{file_obj.name}' -> '{new_name}'")
        shutil.move(str(file_obj), str(dest_path))

        print(f"Normalizing paths in {new_name}...")
        normalize_json_paths(dest_path, media_folder_name="media")

        current_index += 1
        files_moved += 1

    return files_moved


async def main():
    overall_start_time = time.perf_counter()

    with open(CONFIG_PATH) as file:
        config = json.load(file)

    client = discord.Client(request_guilds=False)
    channels_future = asyncio.Future()

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")
        try:
            channels = await discover_channels(client, config)
            channels_future.set_result(channels)
        except Exception as e:
            channels_future.set_exception(e)
        finally:
            print("Closing client...")
            await client.close()

    print("Starting Discord client...")
    await client.start(config["token"])

    try:
        channels = channels_future.result()
    except Exception as e:
        print(f"An error occurred while getting channels: {e}")
        return

    discovery_end_time = time.perf_counter()
    discovery_duration = discovery_end_time - overall_start_time
    formatted_discovery_time = str(timedelta(seconds=int(discovery_duration)))
    print(f"Found {len(channels)} channels in {formatted_discovery_time}.")

    channel_ids = update_channels_ids(channels)

    # Create a mapping of channel ID to object for lookup
    channel_map = {c.id: c for c in channels}
    total_channels = len(channel_ids)

    for i, channel_id in enumerate(channel_ids, start=1):
        channel_start_time = time.perf_counter()

        # Check if we should skip based on last message ID
        channel_obj = channel_map.get(channel_id)
        if (
            channel_obj
            and hasattr(channel_obj, "last_message_id")
            and channel_obj.last_message_id
        ):
            last_archived_id = get_last_archived_message_id(channel_id, OUTPUT_PATH)
            if last_archived_id and str(channel_obj.last_message_id) == str(
                last_archived_id
            ):
                print(
                    f"\n--- [{i}/{total_channels}] Skipping {channel_id} (already up to date) ---"
                )
                continue

        print(f"\n--- [{i}/{total_channels}] Processing {channel_id} ---")

        # Clear temp dir before starting a new channel
        for f in os.listdir(TEMP_DIR):
            try:
                os.remove(os.path.join(TEMP_DIR, f))
            except Exception:
                pass

        cmd_args = [DCE_PATH, "export"] + CHANNEL_EXPORT_OPTIONS

        last_msg_id, files_to_delete, next_part_index = get_resume_point(
            channel_id, OUTPUT_PATH
        )

        is_resuming = False

        if last_msg_id:
            is_resuming = True
            print(f"Resuming after Message ID: {last_msg_id}")
            print(f"Next partition index: {next_part_index}")

            # Delete the incomplete tail files
            for f in files_to_delete:
                print(f"Deleting incomplete tail file: {f.name}")
                os.remove(f)

            # Export to temp directory using --after
            cmd_args.extend(["--after", last_msg_id, "--output", TEMP_DIR])
        else:
            print("Starting fresh export.")
            cmd_args.extend(["--output", OUTPUT_PATH])

        cmd_args.extend(
            [
                "--channel",
                str(channel_id),
                "--token",
                config["token"],
            ]
        )

        # Run the DCE command
        process = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        assert process.stdout is not None, (
            "Process stdout is None despite requesting PIPE"
        )

        # Print DCE output to console
        print()
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            decoded_line = line.decode("utf-8", errors="replace").rstrip()
            if decoded_line:
                print(decoded_line)

        await process.wait()
        print()

        # Resume post-processing
        if is_resuming and process.returncode == 0:
            print("Moving and renaming incremental files...")
            moved_count = process_temp_files(
                channel_id, TEMP_DIR, OUTPUT_PATH, next_part_index
            )
            print(f"Successfully processed {moved_count} new partition files.")

        # Print durations
        channel_end_time = time.perf_counter()
        channel_duration = channel_end_time - channel_start_time
        formatted_channel_time = str(timedelta(seconds=int(channel_duration)))
        total_duration = channel_end_time - overall_start_time
        formatted_total_time = str(timedelta(seconds=int(total_duration)))
        print(
            f"--- Finished [{i}/{total_channels}]. Duration: {formatted_channel_time} | Total Duration: {formatted_total_time} ---\n"
        )

    # Print total duration
    overall_end_time = time.perf_counter()
    total_duration = overall_end_time - overall_start_time
    formatted_total_time = str(timedelta(seconds=int(total_duration)))

    print("==========================================")
    print("All exports completed.")
    print(f"Total Channels: {total_channels}")
    print(f"Total Time Elapsed: {formatted_total_time}")
    print("==========================================")


# Disabled scheduler for now
# async def run_scheduler():
#     while True:
#         print("\n==========================================")
#         print(f"Starting scheduled run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
#         print("==========================================\n")

#         try:
#             await main()
#         except Exception as e:
#             print(f"\nCRITICAL ERROR during export: {e}")
#             print("Waiting for next cycle...")

#         print("Sleeping for 4 hours...")
#         await asyncio.sleep(3600 * 4)


if __name__ == "__main__":
    try:
        # Ensure dirs exist
        os.makedirs(TEMP_DIR, exist_ok=True)
        os.makedirs(OUTPUT_PATH, exist_ok=True)
        os.makedirs(MEDIA_OUTPUT_PATH, exist_ok=True)

        asyncio.run(main())
        # asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        print("\nScript stopped by user.")
