# Stalker

## Description

Stalker is a Discord tool used to monitor a user's activity across various guilds. It provides real-time updates and notifications about the user's interactions and activities.

## Installation

1. Clone this repository to your local machine.
2. Install the required dependencies by running `pip install -r requirements.txt` in your terminal.

## Configuration

The configuration for Stalker is located in `configxd.py`. This file contains the following:

- `stalked`: A list of user IDs to monitor.
- `pathdumps`: The path where dumps will be stored.
- `token`: The Discord token.
- `limit`: The limit for messages.
- `webhooks`: A dictionary of webhooks for different types of notifications.
- `message_contains`: A list of regular expressions to match in messages.
- `matches`: A dictionary of match types to enable or disable.

Update these values as needed for your use case.

## Usage

1. Run the script by typing `python stalker.py` in your terminal.

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

[MIT](https://choosealicense.com/licenses/mit/)
