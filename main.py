import json
import asyncio

# import subprocess
import discord

CONFIG_PATH = "config.json"
OUTPUT_PATH = "output"
MEDIA_OUTPUT_PATH = "output/media"
DCE_PATH = "dce/DiscordChatExporter.Cli"

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
                        if channel.id in config["excluded_channels"]:
                            print(f"Skipped {gen_channel_name(channel)}.")
                            continue

                        if isinstance(channel, discord.TextChannel):
                            channels.append(channel)

                        if isinstance(
                            channel, (discord.TextChannel, discord.ForumChannel)
                        ):
                            threads = [
                                thread
                                async for thread in channel.archived_threads()
                                if str(thread.id) not in config["threads"]
                            ]
                            channels.append(threads)
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
        result = channels_future.result()
        print(f"Data received in main: {result}")
        return result
    except Exception as e:
        print(f"An error occurred during execution: {e}")
        return None

    # for category in config["categories"]:
    #     result = subprocess.run(
    #         [
    #             DCE_PATH,
    #             "export",
    #             *CHANNEL_EXPORT_OPTIONS,
    #             "--channel",
    #             category,
    #             "--token",
    #             config["token"],
    #             "--after",
    #             "2025-12-14 23:59",
    #         ],
    #         stdout=subprocess.PIPE,
    #     )
    #     print(result.stdout.decode())


if __name__ == "__main__":
    asyncio.run(main())
