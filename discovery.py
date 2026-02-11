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
    new_channel_ids = [channel.id for channel in new_channels]

    with open(CHANNEL_IDS_PATH, "w") as file:
        for channel_id in new_channel_ids:
            file.write(f"{channel_id}\n")

    print(f"Saved {len(new_channel_ids)} channels.")
    return new_channel_ids


async def discover_channels(client: discord.Client, config: dict):
    channels: list = []
    seen_ids: set[int] = set()

    # 1. Check the cache
    cached_ids = load_channel_ids()
    for cid in cached_ids:
        try:
            channel = await client.fetch_channel(cid)
            if channel.id not in seen_ids:
                if isinstance(channel, discord.Thread):
                    print(f"Added cached thread {gen_thread_name(channel)}.")
                elif not isinstance(channel, discord.abc.PrivateChannel):
                    print(f"Added cached channel {gen_channel_name(channel)}.")
                else:
                    # Should not happen, Private channels do not belong in a category
                    print(f"Added cached private channel {channel.id}.")

                channels.append(channel)
                seen_ids.add(channel.id)
        except (discord.Forbidden, discord.NotFound):
            print(f"No access to cached channel {cid}. Skipping.")

    # 2. Check the threads in config
    for thread_id in config.get("threads", []):
        try:
            tid = int(thread_id)
            if tid in seen_ids:
                continue

            thread = await client.fetch_channel(tid)
            if not isinstance(thread, discord.Thread):
                print(f"{thread.id} is not a thread!")
                continue

            print(f"Added thread {gen_thread_name(thread)}.")
            channels.append(thread)
            seen_ids.add(thread.id)

        except (discord.Forbidden, discord.NotFound):
            print(f"No access to thread {thread_id}. Skipping.")
        except ValueError:
            print(f"Invalid thread ID in config: {thread_id}")

    # 3. Check the categories
    excluded_ids = {int(i) for i in config.get("excluded_channels", [])}
    for category_id in config.get("categories", []):
        try:
            cid = int(category_id)
            category = await client.fetch_channel(cid)
        except (discord.Forbidden, discord.NotFound):
            print(f"No access to category {category_id}. Skipping.")
            continue
        except ValueError:
            print(f"Invalid category ID in config: {category_id}")
            continue

        if isinstance(category, discord.CategoryChannel):
            # Add text channels and their threads + forum threads
            for channel in category.channels:
                if channel.id in excluded_ids:
                    print(f"Skipped {gen_channel_name(channel)}.")
                    continue

                if channel.id in seen_ids:
                    continue

                if isinstance(channel, discord.TextChannel):
                    print(f"Added channel {gen_channel_name(channel)}.")
                    channels.append(channel)
                    seen_ids.add(channel.id)

                if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                    async for thread in channel.archived_threads(limit=None):
                        if thread.id in seen_ids:
                            continue

                        print(
                            f"Found archived thread {gen_thread_name(thread)} in {gen_channel_name(channel)}."
                        )
                        channels.append(thread)
                        seen_ids.add(thread.id)

        elif isinstance(category, discord.abc.GuildChannel):
            print(f"{category.name} is not a category!")
        else:
            print(f"{category.id} is not a category!")

    update_channels_ids(channels)
    return channels
