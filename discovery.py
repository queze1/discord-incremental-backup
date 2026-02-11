import discord

CHANNEL_IDS_PATH = "channel_ids.txt"


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
        with open(CHANNEL_IDS_PATH) as file:
            return [int(channel_id) for channel_id in file.readlines()]
    except FileNotFoundError:
        print("Channel cache is empty.")
    return []


def update_channels_ids(new_channels):
    old_channel_ids = load_channel_ids()
    new_channel_ids = [channel.id for channel in new_channels]
    combined_channel_ids = list(set(old_channel_ids + new_channel_ids))

    with open(CHANNEL_IDS_PATH, "w") as file:
        for channel_id in combined_channel_ids:
            file.write(f"{channel_id}\n")

    print(f"Saved {len(combined_channel_ids)} channels.")
    return combined_channel_ids


async def discover_channels(client: discord.Client, config: dict):
    channels: list[discord.abc.MessageableChannel] = []

    for thread_id in config["threads"]:
        try:
            thread = await client.fetch_channel(thread_id)
            if not isinstance(thread, discord.Thread):
                print(f"{thread.id} is not a thread!")
                continue

            channels.append(thread)
            print(f"Added {gen_thread_name(thread)}.")
        except (discord.Forbidden, discord.NotFound):
            print(f"No access to thread {thread_id}. Skipping.")

    for category_id in config["categories"]:
        try:
            category = await client.fetch_channel(category_id)
        except (discord.Forbidden, discord.NotFound):
            print(f"No access to category {category_id}. Skipping.")
            continue

        if isinstance(category, discord.CategoryChannel):
            # Add text channels and their threads + forum threads
            for channel in category.channels:
                if str(channel.id) in config["excluded_channels"]:
                    print(f"Skipped {gen_channel_name(channel)}.")
                    continue

                if isinstance(channel, discord.TextChannel):
                    channels.append(channel)

                if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
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

    return channels
