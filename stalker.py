import json
import logging
import os
import asyncio
import contextlib
from datetime import datetime
from io import BytesIO
from secrets import token_hex
from aiohttp import ClientSession
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
    Thread,
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
    Reaction,
    Asset,
)
from discord.abc import Messageable, PrivateChannel, GuildChannel
from httpx import AsyncClient, Response

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
        self.session = AsyncClient()

    async def match(self, obj: Union[Message, Reaction], **kwargs) -> bool | None:
        if isinstance(obj, Reaction):
            return (
                obj.message.author.id in self.gfsaccounts
                or kwargs.get("user").id in self.gfsaccounts
                or (any(
                    pattern.search(obj.message.content)
                    for pattern in configxd.message_contains
                )
                if configxd.matches.get("reacts_to_contains")
                else False)
            )
        if configxd.matches.get("user_mention"):
            for mention in obj.mentions:
                if mention.id in self.gfsaccounts:
                    return True

        if configxd.matches.get("message_contains"):
            for pattern in configxd.message_contains:
                if pattern.search(obj.content):
                    return True
            if obj.reference and isinstance(obj.reference.resolved, Message):
                for pattern in configxd.message_contains:
                    if pattern.search(obj.reference.resolved.content):
                        return True

        return obj.author.id in self.gfsaccounts

    async def history(
        self,
        member: Union[User, Member],
        channel: Union[GuildChannel, PrivateChannel],
        limit: int | None = configxd.limit,
    ) -> List[Message]:
        offset: int = 0
        if isinstance(channel, PrivateChannel):
            url: str = (
                f"https://discord.com/api/v9/channels/{channel.id}/messages/search"
            )
        else:
            url: str = (
                f"https://discord.com/api/v9/guilds/{channel.guild.id}/messages/search"
            )
        msgs: List[Message] = []
        while True:
            request: Response = await self.session.get(
                url=url,
                headers={
                    "Authorization": configxd.token,
                },
                params={
                    "author_id": member.id,
                    "offset": offset,
                    "channel_id": channel.id,
                },
            )
            self.logger.debug(f"Searched {offset} in #{channel} ({channel.id})")
            if request.status_code == 200:
                messages: List = request.json()["messages"]
                if len(messages) == 0:
                    self.logger.info(
                        f"Reached end/No messages in #{channel} ({channel.id}) | @{member} ({member.id})"
                    )
                    return msgs
                for message in messages:
                    try:
                        msgs.append(
                            Message(
                                state=self._connection, data=message[0], channel=channel
                            )
                        )
                    except Exception as e:
                        self.logger.error(e, exc_info=True)
                if len(msgs) >= limit:
                    self.logger.info(
                        f"Reached limit of {limit} messages in #{channel} ({channel.id}) | @{member} ({member.id})"
                    )
                    return msgs
                offset += 25
            elif request.status_code == 429:
                self.logger.warning(
                    f"Rate limited, retrying in {request.json()['retry_after'] + .35}s in #{channel} ({channel.id}) | @{member} ({member.id})"
                )
                await asyncio.sleep(request.json()["retry_after"] + 0.35)
            elif request.status_code == 401:
                self.logger.error(
                    "Unauthorized this client will probably now exit soon :p"
                )
                return msgs

    @staticmethod
    async def readable_channels(
        guild: Guild,
    ) -> List[GuildChannel]:
        return [
            channel
            for channel in (await guild.fetch_channels())
            if hasattr(channel, "history") and not isinstance(channel, Thread)
            if channel.permissions_for(guild.me).read_messages
        ]

    async def messageablejumpurl(self, channel: Messageable) -> str | None:
        with contextlib.suppress(InvalidData, HTTPException, NotFound, Forbidden):
            channel = await self.fetch_channel(channel.id)
            if isinstance(channel, PrivateChannel):
                return f"https://discord.com/channels/@me/{channel.id}"
            else:
                return channel.jump_url if hasattr(channel, "jump_url") else None

    @staticmethod
    async def sizecheck(files: List[File], size: int) -> List[File]:
        if size > FILE_LIMIT:
            path = os.path.join(configxd.pathdumps, f"/{token_hex(50)}.zip")
            zipfile, _ = await zip_files(files)
            with open(path, "wb") as f:
                f.write(zipfile)
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

    async def lmfaoidkwhattoccallthesefuckingthings(
        self, message: Message
    ) -> List[File]:
        files, size = await getfiles(message)
        if files:
            files: List[File] = await self.sizecheck(files=files, size=size)
        return files

    @staticmethod
    async def invoke_webhook(webhook: str, **kwargs) -> None:
        async with ClientSession() as session:
            webhook: Webhook = Webhook.from_url(url=webhook, session=session)
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

    async def on_user_update(self, before: User, after: User) -> None:
        if before.id in self.gfsaccounts:
            self.logger.info(f"User update from {before} ({before.id})")
            embed = Embed(
                color=Colour.dark_embed(),
                timestamp=after.created_at,
                title=f"Profile update from {after} ({after.id})",
            )
            await self.invoke_webhook(
                self.webhooks.get("profile"),
                username=after.name,
                avatar_url=after.avatar.url,
                content="Profile update! :eyes:",
                embed=await dump_user_fields(before, after, embed),
            )

            if before.avatar != after.avatar:
                embed: Embed = Embed(
                    title=f"**new avatar from {after}**",
                    color=Colour.dark_embed(),
                    timestamp=after.created_at,
                )
                avatar: Asset = (
                    after.default_avatar if after.avatar is None else after.avatar
                )
                _type: Literal["gif", "png"] = "gif" if avatar.is_animated() else "png"
                file: File = File(
                    fp=BytesIO(await avatar.read()), filename=f"after.{_type}"
                )
                embed.set_image(url=f"attachment://after.{_type}")

                await self.invoke_webhook(
                    self.webhooks.get("avatars"),
                    username=after.name,
                    avatar_url=avatar.url,
                    file=file,
                    embed=embed,
                )

    async def on_member_boost(self, member: Member) -> None:
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

    async def on_member_update(self, before: Member, after: Member) -> None:
        if after.id in self.gfsaccounts:
            self.logger.info(f"Member update {after}")
            if not before.premium_since and after.premium_since:
                self.dispatch("member_boost", after)
            embed: Embed = Embed(
                title=f"{after.name} member update ^_^",
                description="```\nGuild features\n"
                + "\n".join(after.guild.features)
                + "\n```",
                url=after.guild.vanity_url,
            )
            roles: BytesIO = BytesIO(
                json.dumps(await get_roles(after), indent=4).encode("utf-8")
            )
            await self.invoke_webhook(
                self.webhooks.get("profile"),
                username=after.name,
                avatar_url=after.avatar.url
                if after.avatar
                else after.default_avatar.url,
                content=f"{after.name} member update ^_^",
                embed=await dump_member_fields(before, after, embed),
                files=await self.sizecheck(
                    [File(fp=roles, filename="roles.json")],
                    len(roles.getvalue()),
                ),
            )

    async def _archive(
        self,
        member: Member,
        channel: Union[GuildChannel, PrivateChannel],
    ) -> None:
        messages: List[Message] = await self.history(
            member=member,
            channel=channel,
            limit=configxd.limit,
        )
        if messages:
            self.logger.info(
                f"Archiving {len(messages)} messages from {member} ({member.id}) in {channel} ({channel.id})"
            )
            _messages, _files = await dump_messages(messages)
            files: List[File] = (
                sum([list(file[0]) for file in _files], []) if _files else []
            )
            _zip: Tuple[bytes, int] = await zip_files(files)
            jsondump: BytesIO = BytesIO(
                bytes(json.dumps(_messages, indent=4), encoding="utf-8")
            )
            await self.invoke_webhook(
                self.webhooks.get("dumps"),
                username=member.name,
                avatar_url=member.avatar.url
                if member.avatar
                else member.default_avatar.url,
                content=f"Archived {len(messages)} messages from {member} ({member.id}) in #{channel} ({channel.id})",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    title=f"Archived {len(messages)} messages from {member} ({member.id}) in #{channel} ({channel.id})",
                    url=await self.messageablejumpurl(channel),
                ),
                files=await self.sizecheck(
                    files=[
                        File(fp=BytesIO(_zip[0]), filename="files.zip"),
                        File(
                            fp=jsondump, filename=f"{channel.id}_from_{member.id}.json"
                        ),
                    ],
                    size=_zip[1] + len(jsondump.getvalue()),
                ),
            )

    async def archive_messages(self, member: Member) -> None:
        self.logger.info(f"Archiving messages from {member} ({member.id})")
        await asyncio.gather(
            *[
                self._archive(member, channel)
                for channel in await self.readable_channels(member.guild)
            ]
        )

    async def on_member_remove(self, member: Member) -> None:
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
            await self.archive_messages(member)

    async def on_member_join(self, member: Member) -> None:
        if member.id in self.gfsaccounts:
            self.logger.info(f"{member} joined {member.guild} ({member.guild.id})")
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

    async def on_message(self, message: Message) -> None:
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
            if message.reference and isinstance(message.reference.resolved, Message):
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

    async def on_message_edit(self, before: Message, after: Message) -> None:
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
                    content=f"Edited message {'after' if i else 'before'}! :eyes:",
                    embeds=[
                        await base_message(message=msg),
                    ],
                    files=await self.lmfaoidkwhattoccallthesefuckingthings(message=msg),
                )

    async def on_message_delete(self, message: Message) -> None:
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

    async def _purge(self, messages: List[Message]) -> None:
        _messages, _files = await dump_messages(messages)
        files: List[File] = (
            sum([list(_file[0]) for _file in _files], []) if _files else []
        )
        _zip: Tuple[bytes, int] = await zip_files(files)
        jsondump: BytesIO = BytesIO(
            bytes(json.dumps(_messages, indent=4), encoding="utf-8")
        )
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
                    File(fp=BytesIO(_zip[0]), filename="files.zip"),
                    File(fp=jsondump, filename="purged.json"),
                ],
                size=_zip[1] + len(jsondump.getvalue()),
            ),
        )

    async def on_bulk_message_delete(self, messages: List[Message]) -> None:
        self.logger.info(
            f"Purged {len(messages)} messages in #{messages[0].channel.name} ({messages[0].channel.id})"
        )
        await self._purge(messages)

    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ) -> None:
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

    async def on_guild_remove(self, guild: Guild) -> None:
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

    async def on_reaction_add(
        self, reaction: Reaction, user: Union[User, Member]
    ) -> None:
        if await self.match(reaction, user=user):
            self.logger.info(f"Reaction add from {user} ({user.id}) {reaction.emoji}")
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=user.name,
                avatar_url=user.avatar.url if user.avatar else user.default_avatar.url,
                content="Reaction add! :eyes:",
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    title=f"Reaction add from {user} ({user.id})",
                    description=f"{reaction.emoji} added to message {reaction.message.id} from {user} ({user.id})",
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
    ) -> None:
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
                    title=f"Relationship update from {relationship.user} ({relationship.user.id}) {before.type.name} -> {relationship.type.name}",
                ),
            )

    async def on_relationship_add(self, relationship: Relationship) -> None:
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
                    title=f"Relationship added from {relationship.user} ({relationship.user.id}) ({relationship.type.name})",
                ),
            )

    async def on_relationship_remove(self, relationship: Relationship) -> None:
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


def main() -> None:
    stalker: Client = Stalker()
    stalker.run(configxd.token, log_formatter=miamiloggr())


if __name__ == "__main__":
    main()
