from typing import *
from os import PathLike
from os.path import join
from pathlib import Path
import re

stalked: List[int] = []  # Users to stalk

pathdumps: PathLike = join(Path(__file__).parent.resolve(), "dumps")

token: str = "ADD_YOUR_TOKEN_HERE"

limit: int = 1000

webhooks: Dict[str, str] = {
    "messages": "",
    "profile": "",
    "voice": "",
    "guild": "",
    "purge": "",
    "presence": "",
    "avatars": "",
    "friendships": "",
    "dumps": "",
}  # Edit these with the discord webhooks ur using

message_contains: List[re.Pattern] = [re.compile(r"regex patterns")]

matches: Dict[str, bool] = {
    "user_mention": True,
    "message_contains": False,
    "reacts_to_stalked": True,
}
