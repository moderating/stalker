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
    WebhookMessage,
    File,
    User,
    PartialMessage,
    Colour,
    HTTPException,
    Thread,
    Forbidden,
    NotFound,
    Member,
    VoiceState,
    Relationship,
    Guild,
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
    voicefunc,
    parse_message_content,
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
        logging.getLogger("discord.utils").setLevel(logging.WARNING)
        logging.getLogger("discord.http").setLevel(logging.WARNING)
        self.logger.addHandler(handler)
        self.stalked = configxd.stalked
        self.webhooks = configxd.webhooks
        self.session = AsyncClient()

    async def match(self, obj: Union[Message, Reaction], **kwargs) -> bool | None:
        if isinstance(obj, Reaction):
            return (
                obj.message.author.id in self.stalked
                or kwargs.get("user").id in self.stalked
                or (
                    any(
                        pattern.search(obj.message.content)
                        for pattern in configxd.message_contains
                    )
                    if configxd.matches.get("reacts_to_contains")
                    else False
                )
            )
        if configxd.matches.get("user_mention"):
            for mention in obj.mentions:
                if mention.id in self.stalked:
                    return True

        if configxd.matches.get("message_contains"):
            for pattern in configxd.message_contains:
                if pattern.search(obj.content):
                    return True
            if obj.reference and isinstance(obj.reference.resolved, Message):
                for pattern in configxd.message_contains:
                    if pattern.search(obj.reference.resolved.content):
                        return True

        return obj.author.id in self.stalked

    async def history(
        self,
        member: Union[User, Member],
        channel: Union[GuildChannel, PrivateChannel],
        limit: int = configxd.limit,
    ) -> List[Message]:
        offset: int = 0
        path = (
            f"channels/{channel.id}"
            if isinstance(channel, PrivateChannel)
            else f"guilds/{channel.guild.id}"
        )
        url: str = f"https://discord.com/api/v9/{path}/messages/search"
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
                messages: List[PartialMessage] = request.json().get("messages", [])
                if not len(messages):
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
                offset += len(msgs)
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
    async def invoke_webhook(webhook: str, **kwargs) -> WebhookMessage:
        async with ClientSession() as session:
            webhook: Webhook = Webhook.from_url(url=webhook, session=session)
            return await webhook.send(**kwargs)

    async def on_ready(self):
        self.logger.info(
            f"Stalking {len(self.stalked)} {'person' if len(self.stalked) == 1 else 'people'} in {len(self.guilds)} guild{'' if len(self.guilds) == 1 else 's'} @ {self.user} | {self.user.id}"
        )

    async def on_typing(
        self, channel: Messageable, user: Union[User, Member], when: datetime
    ):
        if user.id in self.stalked:
            self.logger.info(f"{user} is typing in {channel}")
            url = await self.messageablejumpurl(channel)
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=user.name,
                avatar_url=user.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=when,
                    description=f"Typing from {user} ({user.id}) in {channel} ({channel.id})",
                ),
                components=[
                        {
                            "type": 1,
                            "components": [
                                {
                                    "type": 2,
                                    "label": f"Jump to channel {'' if url else '(no jump_url)'}",
                                    "style": 5,
                                    "url": url or "https://discord.com",
                                    "disabled": not url,
                                },
                            ],
                        }
                    ],
            )

    async def on_user_update(self, before: User, after: User) -> None:
        if before.id in self.stalked:
            self.logger.info(f"User update from {before} ({before.id})")
            embed = Embed(
                color=Colour.dark_embed(),
                timestamp=after.created_at,
                title=f"Profile update from {after} ({after.id})",
            )
            await self.invoke_webhook(
                self.webhooks.get("profile"),
                username=after.name,
                avatar_url=after.display_avatar.url,
                content="Profile update! :eyes:",
                embed=await dump_user_fields(before, after, embed),
            )

            if before.avatar != after.avatar:
                embed: Embed = Embed(
                    title=f"**new avatar from {after}**",
                    color=Colour.dark_embed(),
                    timestamp=after.created_at,
                )
                avatar: Asset = after.display_avatar
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
        if member.id in self.stalked:
            self.logger.info(
                f"{member} boosted guild {member.guild} ({member.guild.id})"
            )
            await self.invoke_webhook(
                self.webhooks.get("guild"),
                username=member.name,
                avatar_url=member.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    description=f"{member} ({member.id}) boosted {member.guild} ({member.guild.id})",
                    url=member.guild.vanity_url,
                ),
            )

    async def on_member_update(self, before: Member, after: Member) -> None:
        if after.id in self.stalked:
            self.logger.info(f"Member update {after}")
            if not before.premium_since and after.premium_since:
                self.dispatch("member_boost", after)
            roles: BytesIO = BytesIO(
                json.dumps(await get_roles(after), indent=4).encode("utf-8")
            )
            await self.invoke_webhook(
                self.webhooks.get("profile"),
                username=after.name,
                avatar_url=after.display_avatar.url,
                content=f"{after.name} member update ^_^",
                embed=await dump_member_fields(
                    before, after, Embed(color=Colour.dark_embed())
                ),
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
                sum((list(file[0]) for file in _files), []) if _files else []
            )
            _zip: Tuple[bytes, int] = await zip_files(files)
            jsondump: BytesIO = BytesIO(
                bytes(json.dumps(_messages, indent=4), encoding="utf-8")
            )
            await self.invoke_webhook(
                self.webhooks.get("dumps"),
                username=member.name,
                avatar_url=member.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    description=f"Archived {len(messages)} messages from {member} ({member.id}) in #{channel} ({channel.id})",
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
        if member.id in self.stalked:
            self.logger.info(
                f"{member} left, archiving {configxd.limit or ''} messages"
            )
            await self.invoke_webhook(
                self.webhooks.get("guild"),
                username=member.name,
                avatar_url=member.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    description=f"{member} ({member.id}) left {member.guild} ({member.guild.id}) ",
                ),
            )
            await self.archive_messages(member)

    async def on_member_join(self, member: Member) -> None:
        if member.id in self.stalked:
            self.logger.info(f"{member} joined {member.guild} ({member.guild.id})")
            await self.invoke_webhook(
                self.webhooks.get("guild"),
                username=member.name,
                avatar_url=member.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=member.joined_at,
                    description=f"{member} ({member.id}) joined {member.guild} ({member.guild.id})!",
                ),
            )

    async def on_message(self, message: Message) -> None:
        if await self.match(message):
            self.logger.info(
                f"New message from {message.author} ; {message.clean_content}"
            )
            x_x: Optional[WebhookMessage] = None
            if message.reference and isinstance(message.reference.resolved, Message):
                x_x = await self.invoke_webhook(
                    self.webhooks.get("messages"),
                    username=message.reference.resolved.author.name,
                    avatar_url=message.reference.resolved.author.display_avatar.url,
                    content=await parse_message_content(message.reference.resolved),
                    embeds=message.reference.resolved.embeds,
                    files=await self.lmfaoidkwhattoccallthesefuckingthings(
                        message=message.reference.resolved,
                    ),
                    wait=True,
                    components=[
                        {
                            "type": 1,
                            "components": [
                                {
                                    "type": 2,
                                    "label": "Jump to message",
                                    "style": 5,
                                    "url": message.reference.jump_url,
                                }
                            ]
                            + [
                                {
                                    "type": 2,
                                    "label": f"Sticker: {sticker.name}",
                                    "style": 5,
                                    "url": sticker.url,
                                }
                                for sticker in message.reference.resolved.stickers
                            ],
                        }
                    ],
                )
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=message.author.name + (f" (reply to {x_x.id})" if x_x else ""),
                avatar_url=message.author.display_avatar.url,
                content=await parse_message_content(message),
                embeds=message.embeds,
                files=await self.lmfaoidkwhattoccallthesefuckingthings(message=message),
                components=[
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "label": "Jump to message",
                                "style": 5,
                                "url": message.jump_url,
                            }
                        ]
                        + [
                            {
                                "type": 2,
                                "label": f"Sticker: {sticker.name}",
                                "style": 5,
                                "url": sticker.url,
                            }
                            for sticker in message.stickers
                        ],
                    }
                ],
            )

    async def on_message_edit(self, before: Message, after: Message) -> None:
        if await self.match(before) or await self.match(after):
            self.logger.info(
                f"Edited message from {after.author} ; before: {before.clean_content} ; after: {after.clean_content}"
            )
            for i, msg in enumerate([before, after]):
                await self.invoke_webhook(
                    self.webhooks.get("messages"),
                    username=f"{after.author.name} (edited: {'after' if i else 'before'})",
                    avatar_url=after.author.display_avatar.url,
                    content=await parse_message_content(msg),
                    embeds=msg.embeds,
                    files=await self.lmfaoidkwhattoccallthesefuckingthings(message=msg),
                    components=[
                        {
                            "type": 1,
                            "components": [
                                {
                                    "type": 2,
                                    "label": "Jump to message",
                                    "style": 5,
                                    "url": msg.jump_url,
                                }
                            ]
                            + [
                                {
                                    "type": 2,
                                    "label": f"Sticker: {sticker.name}",
                                    "style": 5,
                                    "url": sticker.url,
                                }
                                for sticker in msg.stickers
                            ],
                        }
                    ],
                )

    async def on_message_delete(self, message: Message) -> None:
        if await self.match(message):
            self.logger.info(
                f"Deleted message from {message.author} ; {message.clean_content}"
            )
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=f"{message.author.name} (Deleted)",
                avatar_url=message.author.display_avatar.url,
                content=await parse_message_content(message),
                embeds=message.embeds,
                files=await self.lmfaoidkwhattoccallthesefuckingthings(message),
                components=[
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "label": f"Sticker: {sticker.name}",
                                "style": 5,
                                "url": sticker.url,
                            }
                            for sticker in message.stickers
                        ],
                    }
                ]
                if message.stickers
                else None,
            )

    async def _purge(self, messages: List[Message]) -> None:
        _messages, _files = await dump_messages(messages)
        files: List[File] = (
            sum((list(_file[0]) for _file in _files), []) if _files else []
        )
        _zip: Tuple[bytes, int] = await zip_files(files)
        jsondump: BytesIO = BytesIO(
            bytes(json.dumps(_messages, indent=4), encoding="utf-8")
        )
        await self.invoke_webhook(
            self.webhooks.get("purge"),
            username="purge",
            avatar_url=self.user.display_avatar.url,
            embed=Embed(
                color=Colour.dark_embed(),
                description=f"> Purged {len(messages)} messages",
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
            f"Purged {len(messages)} messages in #{messages[0].channel} ({messages[0].channel.id})"
        )
        await self._purge(messages)

    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ) -> None:
        if member.id in self.stalked:
            self.logger.info(f"Voice state update from {member} ({member.id})")
            await self.invoke_webhook(
                self.webhooks.get("voice"),
                username=member.name,
                avatar_url=member.display_avatar.url,
                embed=await voicefunc(member, before, after),
            )

    async def on_guild_remove(self, guild: Guild) -> None:
        self.logger.warning(f"Kicked out guild {guild} ({guild.id})")
        await self.invoke_webhook(
            self.webhooks.get("guild"),
            username=guild.name,
            avatar_url=guild.icon.url or self.user.display_avatar.url,
            embed=Embed(
                color=Colour.dark_embed(),
                timestamp=datetime.now(),
                description=f"Kicked out {guild} ({guild.id})",
                url=guild.vanity_url,
            ),
        )

    async def on_reaction_add(
        self, reaction: Reaction, user: Union[User, Member]
    ) -> None:
        if await self.match(reaction, user=user):
            self.logger.info(f"Reaction add from {user} ({user.id}) {reaction.emoji}")
            x_x = await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=user.name,
                avatar_url=user.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    timestamp=datetime.now(),
                    description=f"{reaction.emoji} added to message {reaction.message.id} from {reaction.message.author} ({reaction.message.author.id}) by {user} ({user.id})",
                ),
                wait=True,
                components=[
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "label": "Jump to message",
                                "style": 5,
                                "url": reaction.message.jump_url,
                            }
                        ]}]
            )
            await self.invoke_webhook(
                self.webhooks.get("messages"),
                username=f"{reaction.message.author.name}({x_x.id})",
                avatar_url=reaction.message.author.display_avatar.url,
                content=await parse_message_content(reaction.message),
                embeds=reaction.message.embeds,
                files=await self.lmfaoidkwhattoccallthesefuckingthings(
                    reaction.message
                ),
                components=[
                    {
                        "type": 1,
                        "components": [
                            {
                                "type": 2,
                                "label": "Jump to message",
                                "style": 5,
                                "url": reaction.message.jump_url,
                            }
                        ]
                        + [
                            {
                                "type": 2,
                                "label": f"Sticker: {sticker.name}",
                                "style": 5,
                                "url": sticker.url,
                            }
                            for sticker in reaction.message.stickers
                        ],
                    }
                ],
            )

    async def on_relationship_update(
        self, before: Relationship, relationship: Relationship
    ) -> None:
        if relationship.user.id in self.stalked:
            await self.invoke_webhook(
                self.webhooks.get("friendships"),
                username=relationship.user.name,
                avatar_url=relationship.user.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    title=f"Relationship update from {relationship.user} ({relationship.user.id}) {before.type.name} -> {relationship.type.name}",
                ),
            )

    async def on_relationship_add(self, relationship: Relationship) -> None:
        if relationship.user.id in self.stalked:
            await self.invoke_webhook(
                self.webhooks.get("friendships"),
                username=relationship.user.name,
                avatar_url=relationship.user.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    description=f"Relationship added from {relationship.user} ({relationship.user.id}) ({relationship.type.name})",
                ),
            )

    async def on_relationship_remove(self, relationship: Relationship) -> None:
        if relationship.user.id in self.stalked:
            await self.invoke_webhook(
                self.webhooks.get("friendships"),
                username=relationship.user.name,
                avatar_url=relationship.user.display_avatar.url,
                embed=Embed(
                    color=Colour.dark_embed(),
                    description=f"Relationship removed from {relationship.user} ({relationship.user.id}) removed",
                ),
            )


def main() -> None:
    stalker: Stalker = Stalker()
    stalker.run(configxd.token, log_formatter=miamiloggr())


if __name__ == "__main__":
    main()
