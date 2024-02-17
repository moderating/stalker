import logging
from io import BytesIO
from datetime import datetime
from typing import *
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import md5
from discord import (
    Message,
    HTTPException,
    VoiceState,
    Forbidden,
    NotFound,
    Asset,
    Reaction,
    File,
    Member,
    User,
    Embed,
    Colour,
)
from logger import miamiloggr
from .brah import truncate

logger: logging.Logger = logging.getLogger("dumpers")
logger.setLevel(logging.INFO)
handler: logging.Handler = logging.StreamHandler()
handler.setFormatter(miamiloggr())
logger.addHandler(handler)


async def getfiles(message: Message) -> Tuple[Tuple[File], int]:
    files = []
    counter = 0
    for attachment in message.attachments:
        try:
            files.append(
                await attachment.to_file(
                    filename=f"{md5(bytes(str(attachment.id), encoding='utf-8')).hexdigest()}_{attachment.filename}",
                    use_cached=True,
                )
            )
            counter += attachment.size
        except (HTTPException, Forbidden, NotFound) as e:
            if isinstance(e, HTTPException) and e.code == 0:
                logger.warning(
                    f"Attachment {attachment.id} from {message.author} ({message.author.id}) cant be cached, retrying without cache",
                )
            try:
                files.append(
                    await attachment.to_file(
                        filename=f"{md5(bytes(str(attachment.id), encoding='utf-8')).hexdigest()}_{attachment.filename}",
                        use_cached=False,
                    )
                )
                counter += attachment.size
            except (HTTPException, Forbidden, NotFound) as e:
                logger.error(
                    f"Error getting attachment {attachment.id} from {message.author} ({message.author.id})",
                    exc_info=e,
                )
            except Exception as e:
                logger.error(
                    f"Unknown error getting attachment {attachment.id} from {message.author} ({message.author.id})",
                    exc_info=e,
                )
    return (
        tuple(files),
        counter,
    )


async def dump_reactions(reactions: List[Reaction]):
    return [
        {
            "emoji": str(reaction.emoji),
            "count": reaction.count,
            "me": reaction.me,
        }
        for reaction in reactions
    ]


async def get_roles(member: Member) -> List[Dict]:
    return [
        {
            "name": role.name,
            "id": role.id,
            "color": role.color.value,
            "position": role.position,
            "mentionable": role.mentionable,
            "hoist": role.hoist,
            "managed": role.managed,
            "permissions": [perm for perm, value in role.permissions if value],
            "created_at": role.created_at.strftime("%m/%d/%Y %H:%M:%S %p"),
            "icon": role.display_icon.url
            if isinstance(role.display_icon, Asset)
            else role.display_icon or None,
        }
        for role in member.roles
    ]


async def dump_messages(messages: List[Message]) -> Tuple[List[dict], Set[File]]:
    listXD: List[dict] = []
    fileslist: Set[File] = set()

    for message in messages:
        files = await getfiles(message)
        reply = (
            await dump_messages([message.reference.resolved])
            if message.reference and isinstance(message.reference.resolved, Message)
            else None
        )
        listXD.append(
            {
                "message": message.content,
                "author": {
                    "name": message.author.name,
                    "id": message.author.id,
                    "discriminator": message.author.discriminator,
                },
                "channel": {
                    "name": message.channel.name,
                    "id": message.channel.id,
                    "category": message.channel.category.name
                    if message.channel.category
                    else None,
                },
                "guild": {
                    "name": message.guild.name,
                    "id": message.guild.id,
                    "owner": {
                        "name": message.guild.owner.name,
                        "id": message.guild.owner.id,
                        "discriminator": message.guild.owner.discriminator,
                    }
                    if message.guild.owner
                    else {},
                },
                "embeds": [embed.to_dict() for embed in message.embeds],
                "attachments": [
                    f"<File filename={file.filename} md5={file.md5}>"
                    for file in files[0]
                ],
                "reactions": await dump_reactions(message.reactions),
                "created_at": message.created_at.strftime("%m/%d/%Y %H:%M:%S %p"),
                "reply": reply[0][0] if reply else None,
                "stickers": [
                    {"name": sticker.name, "id": sticker.id, "url": sticker.url}
                    for sticker in message.stickers
                ]
                if message.stickers
                else None,
            }
        )
        fileslist.add(tuple(files))
        fileslist.add(
            tuple(_file for _files in reply[1] for _file in _files) if reply else None
        )
    if None in fileslist:
        fileslist.remove(None)
    return (
        listXD,
        list(fileslist),
    )


async def boost(member: Member) -> datetime | str:
    if member.premium_since:
        return member.premium_since.strftime("%m/%d/%Y %H:%M:%S %p")
    return "❌"


async def zip_files(files: Union[List[File], Set[File], Tuple[File]]):
    buffer = BytesIO()
    added_files = set()

    with ZipFile(
        file=buffer, mode="a", compresslevel=ZIP_DEFLATED, allowZip64=False
    ) as zip_file:
        if not files:
            zip_file.writestr("e", data=b"")
        else:
            for file in files:
                if file not in added_files:
                    zip_file.writestr(file.filename, file.fp.read())
                    added_files.add(file)
                file.fp.seek(0)

    buffer.seek(0)
    return buffer.getvalue(), len(buffer.getvalue())


async def dump_user_fields(before: User, after: User, embed: Embed):
    embed.add_field(
        name="Username",
        value=f"{before}{f' -> {after}' if before.name != after.name or before.discriminator != after.discriminator else ''}",
    )
    embed.add_field(
        name="Avatar",
        value=f"[Before]({before.avatar or before.default_avatar}){f' -> [After]({after.avatar or after.default_avatar})' if before.avatar != after.avatar else ''}",
    )
    embed.add_field(
        name="Banner",
        value=f"{f'[Banner]({after.banner.url})' if after.banner else f'Accent Color: {after.accent_color}'}",
    )

    embed.add_field(
        name="Flags",
        value=f"{after.public_flags.value}",
    )
    try:
        profile = await after.profile()
        embed.add_field(
            name="Bio",
            value=profile.bio or "❌",
        )
        embed.add_field(
            name="Premium",
            value=profile.premium_since.strftime("%m/%d/%Y %H:%M:%S %p")
            if profile.premium_since
            else "❌",
        )
        embed.add_field(
            name="Mutual Guilds",
            value=f"{len(profile.mutual_guilds)}",
        )
        embed.add_field(
            name="Mutual Friends",
            value=f"{len(profile.mutual_friends)}",
        )
    except Exception as e:
        logger.error(
            f"Error getting profile for {after} ({after.id})",
            exc_info=e,
        )
    return embed


async def dump_member_fields(before: Member, after: Member, embed: Embed):
    embed.add_field(
        name="Nickname",
        value=f"{before.nick}{f' -> {str(after.nick)}' if before.nick != after.nick else ''}",
    )
    embed.add_field(
        name="Server profile",
        value=f"Avatar: [Before]({before.display_avatar.url or '❌'})"
        + (
            f" -> [After]({after.display_avatar.url or '❌'})"
            if before.display_avatar != after.display_avatar
            else ""
        ),
    )
    embed.add_field(
        name="Joined At",
        value=f"{after.joined_at.strftime('%m/%d/%Y %H:%M:%S %p')}",
    )
    embed.add_field(
        name="Boosted At",
        value=f"{await boost(before)}{f' -> {await boost(after)}' if before.premium_since != after.premium_since else ''}",
    )
    embed.add_field(
        name="Pending",
        value=f"{'✅' if before.pending else '❌'}{' -> ✅' if after.pending else ' -> ❌' if before.pending != after.pending else ''}",
    )
    embed.add_field(
        name="Timeout",
        value="❌"
        + (
            f" -> ✅ | {after.timed_out_until.strftime('%m/%d/%Y %H:%M:%S %p')}"
            if after.timed_out_until
            else ""
        ),
    )
    return embed


async def voicefunc(member: Member, before: VoiceState, after: VoiceState):
    return Embed(
        color=Colour.dark_embed(),
        description=f"""
        **Voice state update from {member} ({member.id})**
        Channel: {before.channel.jump_url or '❌' if before.channel else '❌'} -> {after.channel.jump_url or '❌' if after.channel else '❌'}
        Muted: {'✅' if before.self_mute or before.mute else '❌' if before else '❌'} -> {'✅' if after.self_mute or after.mute else '❌' if after else '❌'}
        Deafened: {'✅' if before.deaf or before.self_deaf else '❌' if before else '❌'} -> {'✅' if after.deaf or after.self_deaf else '❌' if after else '❌'}
        Streaming: {'✅' if before.self_stream else '❌' if before else '❌'} -> {'✅' if before.self_stream else '❌' if before else '❌'}
        Camera: {'✅' if before.self_video else '❌' if before else '❌'} -> {'✅' if after.self_video else '❌' if after else '❌'}
        """,
    )


async def parse_message_content(message: Message) -> str:
    types = {
        0: message.content,
        1: f"{message.author} added {', '.join([str(m) for m in message.mentions])} to the group",
        2: f"{message.author} removed {', '.join([str(m) for m in message.mentions])} from the group",
        3: f"{message.author} started a call | Participants: {', '.join([str(m) for m in message.call.participants])}"
        if message.call
        else "",
        4: f"{message.author} changed the channel name: {getattr(message.channel, 'name', 'Direct Messages')}",
        5: f"{message.author} changed the channel icon",
        6: f"{message.author} pinned a [message](https://discord.com/channels/{getattr(message.guild, 'id', '@me')}/{message.reference.channel_id}/{message.reference.message_id})"
        if message.reference
        else "",
        7: f"{message.author} joined [{message.guild}](https://discord.com/channels/{getattr(message.guild, 'id', '@me')})!",
        8: f"{message.author} has boosted {f'{message.content} times' if message.content else ''}",
        19: message.content,
    }
    return (
        types.get(message.type.value, message.content or message.type.name) or "\u200b"
    )

async def build_components(message: Message):
    return [
                        {
                            "type": 1,
                            "components": [
                                {
                                    "type": 2,
                                    "label": "Jump to message",
                                    "style": 5,
                                    "url": message.reference.jump_url,
                                },
                                {    "type": 2,
                                    "label": f"{truncate(getattr(getattr(message, 'guild', None), 'name', '@me'), limit=39)}/{truncate(getattr(message.channel, 'name', 'Direct messages'), limit=40)}",
                                    "style": 5,
                                    "url": message.channel.jump_url,
                                    "disabled": True
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
                    ]
