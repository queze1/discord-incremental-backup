import asyncio
from datetime import timedelta
import json
import time

import discord

DCE_PATH = "dce/DiscordChatExporter.Cli"

CONFIG_PATH = "config.json"
CHANNEL_CACHE_PATH = "channel_cache.txt"
OUTPUT_PATH = "output"
MEDIA_OUTPUT_PATH = "output/media"

# 1k messages
PARTITION_LENGTH = "1000"

CHANNEL_EXPORT_OPTIONS = [
    "--fuck-russia",
    "--output",
    OUTPUT_PATH,
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


def gen_channel_name(channel: discord.abc.GuildChannel):
    channel_name = ""
    if channel.category:
        channel_name += f"{channel.category.name} / "
    channel_name += channel.name
    return channel_name


def gen_thread_name(thread: discord.Thread):
    thread_name = ""
    if thread.channel:
        thread_name += f"{gen_channel_name(thread.channel)} / "
    thread_name += thread.name
    return thread_name


def load_channel_ids():
    try:
        with open(CHANNEL_CACHE_PATH) as file:
            return [int(channel_id) for channel_id in file.readlines()]
    except FileNotFoundError:
        print("Channel cache is empty.")
    return []


def update_channels_ids(new_channels):
    old_channel_ids = load_channel_ids()
    new_channel_ids = [channel.id for channel in new_channels]
    combined_channel_ids = list(set(old_channel_ids + new_channel_ids))

    with open(CHANNEL_CACHE_PATH, "w") as file:
        for channel_id in combined_channel_ids:
            file.write(f"{channel_id}\n")

    print(f"Saved {len(combined_channel_ids)} channels.")
    return combined_channel_ids


async def main():
    with open(CONFIG_PATH) as file:
        config = json.load(file)

    client = discord.Client(request_guilds=False)
    channels_future = asyncio.Future()

    @client.event
    async def on_ready():
        print(f"Logged in as {client.user}")

        try:
            channels = []

            for thread_id in config["threads"]:
                thread = await client.fetch_channel(thread_id)
                if not isinstance(thread, discord.Thread):
                    print(f"{thread.id} is not a thread!")
                    continue

                channels.append(thread)
                print(f"Added {gen_thread_name(thread)}.")

            for category_id in config["categories"]:
                category = await client.fetch_channel(category_id)
                if isinstance(category, discord.CategoryChannel):
                    # Add text channels and their threads + forum threads
                    for channel in category.channels:
                        if str(channel.id) in config["excluded_channels"]:
                            print(f"Skipped {gen_channel_name(channel)}.")
                            continue

                        if isinstance(channel, discord.TextChannel):
                            channels.append(channel)

                        if isinstance(
                            channel, (discord.TextChannel, discord.ForumChannel)
                        ):
                            threads = [
                                thread
                                async for thread in channel.archived_threads(limit=None)
                                if str(thread.id) not in config["threads"]
                            ]
                            channels += threads
                            print(
                                f"Found {gen_channel_name(channel)} and {len(threads)} threads."
                            )

                elif isinstance(category, discord.abc.GuildChannel):
                    print(f"{category.name} is not a category!")
                else:
                    print(f"{category.id} is not a category!")

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

    channel_ids = update_channels_ids(channels)
    total_channels = len(channel_ids)

    overall_start_time = time.perf_counter()
    for i, channel_id in enumerate(channel_ids, start=1):
        channel_start_time = time.perf_counter()
        print(
            f"\n--- [{i}/{total_channels}] Starting Export for Channel ID: {channel_id} ---"
        )

        args = [
            DCE_PATH,
            "export",
            *CHANNEL_EXPORT_OPTIONS,
            "--channel",
            str(channel_id),
            "--token",
            config["token"],
        ]

        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        assert process.stdout is not None, (
            "Process stdout is None despite requesting PIPE"
        )

        # Print DCE output to console
        while True:
            line = await process.stdout.readline()
            if not line:
                break

            decoded_line = line.decode("utf-8", errors="replace").rstrip()
            if decoded_line:
                print(decoded_line)

        await process.wait()

        # Print durations
        channel_end_time = time.perf_counter()
        channel_duration = channel_end_time - channel_start_time
        formatted_channel_time = str(timedelta(seconds=int(channel_duration)))
        total_duration = channel_end_time - overall_start_time
        formatted_total_time = str(timedelta(seconds=int(total_duration)))
        print(
            f"--- Finished [{i}/{total_channels}]. Duration: {formatted_channel_time}; Total Duration: {formatted_total_time} ---\n"
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


if __name__ == "__main__":
    asyncio.run(main())
