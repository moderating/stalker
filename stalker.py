import json
import contextlib
import logging
from datetime import datetime
from io import BytesIO
from secrets import token_hex
from typing import *
from discord import (
    Client,
    Embed,
    Message,
    File,
    User,
    VoiceChannel,
    Colour,
    HTTPException,
    Forbidden,
    NotFound,
    Member,
    VoiceState,
    Relationship,
    Guild,
    TextChannel,
    ForumChannel,
    Webhook,
    InvalidData,
    Thread,
    Reaction,
)
from discord.abc import Messageable, GuildChannel, PrivateChannel
from aiohttp import ClientSession
import configxd
from consts import *
from logger import miamiloggr
from helpers.dumpers import (
    dump_messages,
    zip_files,
    dump_user_fields,
    getfiles,
    dump_member_fields,
    get_roles,
    base_message,
    voicefunc,
)

class Stalker(Client):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.logger: logging.Logger = logging.getLogger("stalker")
        self.logger.setLevel(logging.DEBUG)
        handler: logging.Handler = logging.StreamHandler()
        handler.setFormatter(miamiloggr())
        self.logger.addHandler(handler)
        self.gfsaccounts = configxd.stalked
        self.webhooks = configxd.webhooks

    async def match(self, obj: Union[Message, Reaction], **kwargs) -> bool | None:
        if isinstance(obj, Reaction):
            return (
                obj.message.author.id in self.gfsaccounts
                or kwargs.get("user").id in self.gfsaccounts
            )
        else:
            if configxd.matches.get("user_mention"):
                for mention in obj.mentions:
                    if mention.id in self.gfsaccounts:
                        return True

            if configxd.matches.get("message_contains"):
                for pattern in configxd.message_contains:
                    if pattern.search(obj.content):
                        return True

            return True if obj.author.id in self.gfsaccounts else False

    async def userhistory(
        self,
        member: Union[User, Member],
        channel: Union[TextChannel, ForumChannel, VoiceChannel],
        limit: int = configxd.limit or 1000,
    ):
        with contextlib.suppress(Forbidden):
            messages = [message async for message in channel.history(limit=None)]
            new_messages = []
            counter = 0
            while not counter >= limit:
                for message in messages:
                    if message.author == member:
                        counter += 1
                        new_messages.append(message)
            return new_messages
        return []

    async def readable_channels(self, guild: Guild):
        return [
            channel
            for channel in (await guild.fetch_channels())
            if isinstance(channel, TextChannel)
            or isinstance(channel, ForumChannel)
            or isinstance(channel, VoiceChannel)
            and channel.permissions_for(guild.me).read_messages
        ]

    async def messageablejumpurl(self, channel: Messageable) -> str | bool:
        with contextlib.suppress(InvalidData, HTTPException, NotFound, Forbidden):
            channel = await self.fetch_channel(channel.id)
            if isinstance(channel, GuildChannel):
                return channel.jump_url
            elif isinstance(channel, PrivateChannel):
                return f"https://discord.com/channels/@me/{channel.id}"
            elif isinstance(channel, Thread):
                return channel.channel.jump_url + "/" + str(channel.id)

    async def sizecheck(self, files: List[File], size: int):
        if size > FILE_LIMIT:
            path = configxd.pathdumps + f"/{token_hex(32)}.zip"
            with open(path, "wb") as f:
                f.write(await zip_files(files))
            files = [
                File(
                    fp=BytesIO(
                        f"Files were too big to send\nFile saved at: {path}".encode(
                            "utf-8"
                        )
                    ),
                    filename="files.txt",
                )
            ]
        return files

    async def lmfaoidkwhattoccallthesefuckingthings(self, message: Message):
        files, size = await getfiles(message)
        if files:
            files = await self.sizecheck(files=files, size=size)
        return files

    async def invoke_webhook(self, webhook: str, **kwargs) -> None:
        async with ClientSession() as session:
            webhook: Webhook = Webhook.from_url(webhook, session=session)
            await webhook.send(**kwargs)

    async def on_ready(self):
        self.logger.info(
            f"Stalking ekitten in {len(self.guilds)} guilds @ {self.user} | {self.user.id}"
        )

    async def on_typing(
        self, channel: Messageable, user: Union[User, Member], when: datetime
    ):
        if user.id in self.gfsaccounts:
            self.logger.info(f"{user} is typing in {channel}")
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=user.name,
                avatar_url=user.avatar.url if user.avatar else user.default_avatar.url,
                content="Typing! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=when,
                    description=f"Typing from {user} ({user.id}) in {channel} ({channel.id})",
                    title=f"**{user} ({user.id}) typing**",
                    url=await self.messageablejumpurl(channel),
                ),
            )

    async def on_user_update(self, before: User, after: User):
        if before.id in self.gfsaccounts:
            self.logger.info(f"User update from {before} ({before.id})")
            embed = Embed(
                color=Colour.dark_embed(),
                timestamp=after.created_at,
                title=f"Profile update from {after} ({after.id})",
                description=f"If theres no change here check <#>",
            )
            await self.invoke_webhook(
                self.webhooks.get("profile"),
                username=after.name,
                avatar_url=after.avatar.url,
                content="Profile update! :eyes:",
                embed=await dump_user_fields(before, after, embed),
            )

            if before.avatar != after.avatar:
                embed = Embed(
                    title=f"**new avatar from {after}**",
                    color=Colour.dark_embed(),
                    timestamp=after.created_at,
                )
                avatar = after.default_avatar if after.avatar is None else after.avatar
                type = "gif" if avatar.is_animated() else "png"
                file = File(fp=BytesIO(await avatar.read()), filename=f"after.{type}")
                embed.set_image(url=f"attachment://after.{type}")

                await self.invoke_webhook(
                    self.webhooks.get("avatars"),
                    username=after.name,
                    avatar_url=avatar.url,
                    file=file,
                    embed=embed,
                )

    async def on_member_boost(self, member: Member):
        if member.id in self.gfsaccounts:
            self.logger.info(
                f"{member} boosted guild {member.guild} ({member.guild.id})"
            )
            await self.invoke_webhook(
                self.webhooks.get("guild"),
                username=member.name,
                avatar_url=member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                content=f"{member} ({member.id}) boosted a server! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    title=f"{member} ({member.id}) boosted {member.guild} ({member.guild.id})",
                    url=member.guild.vanity_url,
                ),
            )

    async def on_member_update(self, before: Member, after: Member):
        if after.id in self.gfsaccounts:
            self.logger.info(f"Member update {after}")
            if not before.premium_since and after.premium_since:
                self.dispatch("member_boost", after)
            embed = Embed(
                title=f"{after.name} member update ^_^",
                description="```\nGuild features\n"
                + "\n".join(after.guild.features)
                + "\n```",
                url=after.guild.vanity_url,
            )
            roles = json.dumps(await get_roles(after), indent=4)
            await self.invoke_webhook(
                self.webhooks.get("profile"),
                username=after.name,
                avatar_url=after.avatar.url
                if after.avatar
                else after.default_avatar.url,
                content=f"{after.name} member update ^_^",
                embed=await dump_member_fields(before, after, embed),
                files=await self.sizecheck(
                    [File(fp=BytesIO(roles.encode("utf-8")), filename="roles.json")],
                    len(roles.encode("utf-8")),
                ),
            )

    async def on_member_remove(self, member: Member):
        if member.id in self.gfsaccounts:
            self.logger.info(
                f"{member} left, archiving {configxd.limit or ''} messages"
            )
            await self.invoke_webhook(
                self.webhooks.get("guild"),
                username=member.name,
                avatar_url=member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                content=f"{member} ({member.id}) left! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=member.created_at,
                    title=f"{member} ({member.id}) left {member.guild} ({member.guild.id}) ",
                ),
            )

            _messages = [
                await dump_messages(
                    [msg for msg in await self.userhistory(member, channel, limit=configxd.limit) if msg]
                )
                for channel in (await self.readable_channels(member.guild))
            ]
            files = sum(
                [
                    file[0]
                    for messages in _messages
                    for file in messages[1]
                    if messages[1]
                ],
                [],
            )
            _messages = sum([messages[0]
                            for messages in _messages if messages[0]], [])
            x_x = json.dumps(_messages, indent=4)
            intoxicated = BytesIO(bytes(x_x, encoding="utf-8"))
            zip = await zip_files(files)
            await self.invoke_webhook(
                self.webhooks.get("dumps"),
                username="dumps",
                avatar_url=self.user.avatar.url,
                content="dump! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    title=f"dumped {len(_messages)} messages",
                ),
                files=await self.sizecheck(
                    files=[
                        File(fp=BytesIO(zip[0]), filename="files.zip"),
                        File(fp=intoxicated, filename="dumpd.json"),
                    ],
                    size=zip[1] + len(intoxicated.getvalue()),
                ),
            )

    async def on_member_join(self, member: Member):
        if member.id in self.gfsaccounts:
            self.logger.info(
                f"{member} joined {member.guild} ({member.guild.id})")
            await self.invoke_webhook(
                self.webhooks.get("guild"),
                username=member.name,
                avatar_url=member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                content=f"{member} ({member.id}) Joined {member.guild} ({member.guild.id})! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=member.joined_at,
                    title=f"{member} ({member.id})",
                ),
            )

    async def on_message(self, message: Message):
        if await self.match(message):
            self.logger.info(
                f"New message from {message.author} ; {message.clean_content}"
            )

            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=message.author.name,
                avatar_url=message.author.avatar.url
                if message.author.avatar
                else message.author.default_avatar.url,
                content="New message! :eyes:",
                embed=await base_message(message),
                files=await self.lmfaoidkwhattoccallthesefuckingthings(message=message),
            )
            if message.reference and isinstance(
                    message.reference.resolved, Message):
                await self.invoke_webhook(
                    self.webhooks.get("messages"),
                    username=message.author.name,
                    avatar_url=message.reference.resolved.author.avatar.url
                    if message.reference.resolved.author.avatar
                    else message.reference.resolved.author.default_avatar.url,
                    content=f"The replied message from {message.id} :eyes:",
                    embed=await base_message(message.reference.resolved),
                    files=await self.lmfaoidkwhattoccallthesefuckingthings(
                        message=message.reference.resolved
                    ),
                )

    async def on_message_edit(self, before: Message, after: Message):
        if await self.match(before) or await self.match(after):
            self.logger.info(
                f"Edited message from {after.author} ; before: {before.clean_content} ; after: {after.clean_content}"
            )
            for i, msg in enumerate([before, after]):
                await self.invoke_webhook(
                    self.webhooks.get("messages"),
                    username=after.author.name,
                    avatar_url=after.author.avatar.url
                    if after.author.avatar
                    else after.author.default_avatar.url,
                    content=f"Edited message {'before' if i == 0 else 'after'}! :eyes:",
                    embeds=[
                        await base_message(message=msg),
                    ],
                    files=await self.lmfaoidkwhattoccallthesefuckingthings(message=msg),
                )

    async def on_message_delete(self, message: Message):
        if await self.match(message):
            self.logger.info(
                f"Deleted message from {message.author} ; {message.clean_content}"
            )
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=message.author.name,
                avatar_url=message.author.avatar.url
                if message.author.avatar
                else message.author.default_avatar.url,
                content="Deleted message! :eyes:",
                embed=await base_message(message),
                files=await self.lmfaoidkwhattoccallthesefuckingthings(message),
            )

    async def on_bulk_message_delete(self, messages: List[Message]):
        self.logger.info(f"Purged {len(messages)} messages")
        _messages = await dump_messages(messages)
        files = sum([file[0] for file in _messages[1]],
                    []) if _messages[1] else []
        _messages = _messages[0]
        zip = await zip_files(files)
        jsondump = BytesIO(
            bytes(
                json.dumps(
                    _messages,
                    indent=4),
                encoding="utf-8"))
        await self.invoke_webhook(
            self.webhooks.get("purge"),
            username="purge",
            avatar_url=self.user.avatar.url
            if self.user.avatar
            else self.user.default_avatar.url,
            content="Purge! :eyes:",
            embed=Embed(
                color=Colour.dark_embed(),
                title=f"Purged {len(messages)} messages",
            ),
            files=await self.sizecheck(
                files=[
                    File(fp=BytesIO(zip[0]), filename="files.zip"),
                    File(fp=jsondump, filename="purged.json"),
                ],
                size=zip[1] + len(jsondump.getvalue()),
            ),
        )

    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        if member.id in self.gfsaccounts:
            self.logger.info(f"Voice state update from {member} ({member.id})")
            await self.invoke_webhook(
                self.webhooks.get("voice"),
                username=member.name,
                avatar_url=member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                content="Voice state update! :eyes:",
                embed=await voicefunc(member, before, after),
            )

    async def on_guild_remove(self, guild: Guild):
        self.logger.warning(f"Kicked out guild {guild} ({guild.id})")
        await self.invoke_webhook(
            self.webhooks.get("guild"),
            username=guild.name,
            avatar_url=guild.icon.url,
            content="Kicked out guild! :eyes:",
            embed=Embed(
                color=Colour.dark_embed(),
                timestamp=datetime.now(),
                title=f"Kicked out {guild} ({guild.id})",
                url=guild.vanity_url,
            ),
        )

    async def on_reaction_add(self, reaction: Reaction, user: Union[User, Member]):
        if await self.match(reaction, user=user):
            self.logger.info(
                f"Reaction add from {user} ({user.id}) {reaction.emoji}")
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=user.name,
                avatar_url=user.avatar.url if user.avatar else user.default_avatar.url,
                content="Reaction add! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    title=f"Reaction add from {user} ({user.id})",
                    description=f"Reaction add from {user} ({user.id}), {reaction.emoji} to message {reaction.message.id}",
                ),
            )
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=reaction.message.author.name,
                avatar_url=reaction.message.author.avatar.url
                if reaction.message.author.avatar
                else reaction.message.author.default_avatar.url,
                content="Message being reacted to :eyes:",
                embed=await base_message(reaction.message),
                files=await self.lmfaoidkwhattoccallthesefuckingthings(
                    reaction.message
                ),
            )

    async def on_relationship_update(
        self, before: Relationship, relationship: Relationship
    ):
        if relationship.user.id in self.gfsaccounts:
            await self.invoke_webhook(
                self.webhooks.get("friendships"),
                username=relationship.user.name,
                avatar_url=relationship.user.avatar.url
                if relationship.user.avatar
                else relationship.user.default_avatar.url,
                content=f"{relationship.user} ({relationship.user.id}) {relationship.type}",
                embed=Embed(
                    color=Colour.dark_embed(),
                    title=f"Relationship update from {relationship.user} ({relationship.user.id}) {before.type} -> {relationship.type.name}",
                ),
            )

    async def on_relationship_add(self, relationship: Relationship):
        if relationship.user.id in self.gfsaccounts:
            await self.invoke_webhook(
                self.webhooks.get("friendships"),
                username=relationship.user.name,
                avatar_url=relationship.user.avatar.url
                if relationship.user.avatar
                else relationship.user.default_avatar.url,
                content=f"{relationship.user} ({relationship.user.id}) added",
                embed=Embed(
                    color=Colour.dark_embed(),
                    title=f"Relationship added from {relationship.user} ({relationship.user.id}) (user sent friend request {relationship.type.name})",
                ),
            )

    async def on_relationship_remove(self, relationship: Relationship):
        if relationship.user.id in self.gfsaccounts:
            await self.invoke_webhook(
                self.webhooks.get("friendships"),
                username=relationship.user.name,
                avatar_url=relationship.user.avatar.url
                if relationship.user.avatar
                else relationship.user.default_avatar.url,
                content=f"{relationship.user} ({relationship.user.id}) removed",
                embed=Embed(
                    color=Colour.dark_embed(),
                    title=f"Relationship removed from {relationship.user} ({relationship.user.id}) removed",
                ),
            )


def main():
    stalker = Stalker()
    stalker.run(configxd.token, log_formatter=miamiloggr())


if __name__ == "__main__":
    main()
