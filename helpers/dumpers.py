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


logger: logging.Logger = logging.getLogger("dumpers")
logger.setLevel(logging.INFO)
handler: logging.Handler = logging.StreamHandler()
handler.setFormatter(miamiloggr())
logger.addHandler(handler)


async def getfiles(message: Message) -> Tuple[List[File], int]:
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
        files,
        counter,
    )


async def dump_reactions(reactions: List[Reaction]):
    return [
        {"emoji": reaction.emoji, "count": reaction.count, "me": reaction.me}
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


async def dump_messages(messages: List[Message]) -> Tuple[List[dict], List[File]]:
    listXD: List[dict] = []
    fileslist: List[File] = []
    added_files = set()

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
                    f"<File filename={file.filename}>" for file in files[0] if file.filename not in added_files
                ],
                "reactions": await dump_reactions(message.reactions),
                "created_at": message.created_at.strftime("%m/%d/%Y %H:%M:%S %p"),
                "reply": reply[0] if reply else None,
                "sticker": [
                    {"name": sticker.name, "id": sticker.id, "url": sticker.url}
                    for sticker in message.stickers
                ]
                if message.stickers
                else None,
            }
        )
        if files is not None:
            fileslist.append(files)
            added_files.update([file.filename for file in files[0]])

        if reply is not None:
            fileslist.append([f for l in reply[1] for f in l if f.filename not in added_files])
            added_files.update([file.filename for l in reply[1] for file in l])
    return (
        listXD,
        [files for files in fileslist if files],
    )


async def boost(member: Member) -> datetime | str:
    if member.premium_since:
        return member.premium_since.strftime("%m/%d/%Y %H:%M:%S %p")
    return "❌"


async def zip_files(files: List[File]):
    buffer = BytesIO()
    added_files = set()

    with ZipFile(buffer, "a", ZIP_DEFLATED, False) as zip_file:
        if not files:
            zip_file.writestr("empty", b"")
        else:
            for file in files:
                if file.filename not in added_files:
                    zip_file.writestr(file.filename, file.fp.read())
                    added_files.add(file.filename)
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
        name="Banner", value=f"[After]({after.banner or after.accent_color})"
    )

    embed.add_field(
        name="Flags",
        value=f"{after.public_flags}",
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
        value=f"{before.nick}{' -> ' + str(after.nick) if before.nick != after.nick else ''}",
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
        value=f"❌"
        + (
            f" -> ✅ | {after.timed_out_until.strftime('%m/%d/%Y %H:%M:%S %p')}"
            if after.timed_out_until
            else ""
        ),
    )
    return embed


async def base_message(message: Message):
    embed = Embed(
        description=message.content,
        color=Colour.dark_embed(),
        timestamp=message.created_at,
        title=f"New message from {message.author} in #{message.channel}",
        url=message.jump_url,
    )
    embed.add_field(
        name="Message",
        value=f"[{message.id}]({message.jump_url})",
    )
    embed.add_field(
        name="Author",
        value=f"[{message.author}](https://discord.com/users/{message.author.id})",
    )
    embed.add_field(
        name="Channel",
        value=f"[{message.channel}](https://discord.com/channels/{'@me' if not message.guild else message.guild.id}/{message.channel.id})",
    )
    embed.add_field(
        name="Guild",
        value=f"{message.guild} ({message.guild.id})"
        if message.guild
        else "No guild found",
    )
    embed.add_field(
        name="Attachments",
        value=f"{len(message.attachments)} attachments",
    )
    embed.add_field(
        name="Embeds",
        value=f"{len(message.embeds)} embeds",
    )
    embed.add_field(
        name="Reactions",
        value=f"{len(message.reactions)} reactions",
    )
    embed.add_field(
        name="Sticker",
        value=f"[{message.stickers[0].name} - {message.stickers[0].id}]({message.stickers[0].url})"
        if message.stickers
        else "❌",
    )
    embed.add_field(
        name="Reply",
        value=f"[{message.reference.resolved.author} - message: {message.reference.resolved.id}]({message.reference.resolved.jump_url})"
        if message.reference and isinstance(message.reference.resolved, Message)
        else "❌",
    ),
    embed.add_field(
        name="Pinned?",
        value=f"{'✅' if message.pinned else '❌'}",
    ),
    embed.add_field(
        name="Mentions",
        value=f"{len(message.mentions)} mentions",
    )
    return embed

async def voicefunc(member: Member, before: VoiceState, after: VoiceState):
        embed = Embed(
            color=Colour.dark_embed(),
            title=f"Voice state update from {member} ({member.id})",
            description=f"**Voice state update from {member} ({member.id}) ^_^**",
        )
        embed.add_field(
            name="Channel?",
            value=f"{before.channel.jump_url or '❌' if before.channel else '❌'} -> {after.channel.jump_url or '❌' if after.channel else '❌'}",
        )
        embed.add_field(
            name="Muted?",
            value=f"{'✅' if before.self_mute or before.mute else '❌' if before else '❌'} -> {'✅' if after.self_mute or after.mute else '❌' if after else '❌'}",
        )
        embed.add_field(
            name="Deafened?",
            value=f"Before: {'✅' if before.self_deaf or before.self_deaf else '❌' if before else '❌'} -> {'✅' if after.self_deaf or after.self_deaf else '❌' if after else '❌'}",
        )
        embed.add_field(
            name="Streaming?",
            value=f"Before: {'✅' if before.self_stream else '❌' if before else '❌'} -> {'✅' if before.self_stream else '❌' if before else '❌'}",
        )
        embed.add_field(
            name="Cammed up?",
            value=f"Before: {'✅' if before.self_video else '❌' if before else '❌'} -> {'✅' if after.self_video else '❌' if after else '❌'}",
        )
        return embed
