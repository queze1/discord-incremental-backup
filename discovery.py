import discord

CHANNEL_IDS_PATH = "channel_ids.txt"


def get_display_name(obj):
    name = f"{obj.category.name} / " if getattr(obj, "category", None) else ""
    if isinstance(obj, discord.Thread) and obj.channel:
        name = f"{get_display_name(obj.channel)} / "
    return f"{name}{obj.name}"


class ChannelCollector:
    def __init__(self, client: discord.Client):
        self.client = client
        self.channels: list = []
        self.seen_ids: set[int] = set()

    async def add_by_id(self, channel_id: int, context_label=""):
        """Fetch a channel and add it if it hasn't been seen."""
        if not channel_id or channel_id in self.seen_ids:
            return

        try:
            channel = await self.client.fetch_channel(channel_id)
            self._add_channel_object(channel, context_label)
        except (discord.Forbidden, discord.NotFound):
            print(f"No access to {context_label} {channel_id}. Skipping.")
        except Exception as e:
            print(f"Error fetching {channel_id}: {e}")

    def _add_channel_object(self, channel, context_label=""):
        if channel.id in self.seen_ids:
            return

        if isinstance(channel, discord.abc.PrivateChannel):
            return

        label = "thread" if isinstance(channel, discord.Thread) else "channel"
        if context_label:
            label = f"{context_label} {label}"

        print(f"Added {label} {get_display_name(channel)}.")
        self.channels.append(channel)
        self.seen_ids.add(channel.id)


def load_channel_ids():
    try:
        with open(CHANNEL_IDS_PATH) as file:
            return [int(channel_id) for channel_id in file.readlines()]
    except FileNotFoundError:
        print("Channel cache is empty.")
    return []


def save_channel_ids(channels):
    with open(CHANNEL_IDS_PATH, "w") as file:
        for channel in channels:
            file.write(f"{channel.id}\n")

    print(f"Saved {len(channels)} channels.")


async def discover_channels(client: discord.Client, config: dict):
    collector = ChannelCollector(client)

    # 1. Process cache
    for cid in load_channel_ids():
        await collector.add_by_id(cid, "cached")

    # 2. Process config threads
    for tid in config.get("threads", []):
        await collector.add_by_id(int(tid), "thread")

    # 3. Process categories
    excluded_ids = {int(i) for i in config.get("excluded_channels", [])}
    for category_id in config.get("categories", []):
        try:
            category = await client.fetch_channel(int(category_id))
            if not isinstance(category, discord.CategoryChannel):
                print(f"{category_id} is not a category!")
                continue

            for channel in category.channels:
                if channel.id in excluded_ids:
                    continue

                # Add the channel itself
                if isinstance(channel, discord.TextChannel):
                    collector._add_channel_object(channel)

                # Add archived threads
                if isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
                    async for thread in channel.archived_threads(limit=None):
                        collector._add_channel_object(thread, "archived thread")

        except (discord.Forbidden, discord.NotFound):
            print(f"No access to category {category_id}. Skipping.")

    save_channel_ids(collector.channels)
    return collector.channels
