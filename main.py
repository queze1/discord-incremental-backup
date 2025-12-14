import json
import subprocess

CONFIG_PATH = "config.json"
DCE_PATH = "dce/DiscordChatExporter.Cli"
OUTPUT_PATH = "output"
MEDIA_OUTPUT_PATH = "output/media"


def main():
    with open(CONFIG_PATH) as file:
        config = json.load(file)

    for category in config["categories"]:
        result = subprocess.run(
            [
                DCE_PATH,
                "export",
                "--fuck-russia",
                "--channel",
                category,
                "--token",
                config["token"],
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
                "--after",
                "2025-12-14 23:59",
            ],
            stdout=subprocess.PIPE,
        )
        print(result.stdout.decode())


if __name__ == "__main__":
    main()
