from discord import (
    Spotify,
    Activity,
    CustomActivity,
    Game,
)


async def get_presences(activities):
    presences = []
    for activity in activities:
        if isinstance(activity, Activity):
            presences.append(
                {
                    "name": activity.name,
                    "type": activity.type,
                    "url": activity.url,
                    "created_at": activity.created_at.strftime("%m/%d/%Y %H:%M:%S %p"),
                    "assets": activity.assets,
                    "buttons": activity.buttons,
                    "party": activity.party,
                    "state": activity.state,
                    "details": activity.details,
                    "timestamps": activity.timestamps,
                    "emoji": {
                        "id": activity.emoji.id,
                        "name": activity.emoji.name,
                        "animated": activity.emoji.animated,
                        "url": activity.emoji.url,
                    }
                    if activity.emoji
                    else None,
                }
            )
        elif isinstance(activity, Spotify):
            presences.append(
                {
                    "name": activity.name,
                    "album": activity.album,
                    "artists": activity.artists,
                    "duration": activity.duration,
                    "created_at": activity.created_at.strftime("%m/%d/%Y %H:%M:%S %p"),
                    "title": activity.title,
                    "track": {
                        "id": activity.track_id,
                        "url": activity.track_url,
                        "name": activity.title,
                    },
                }
            )
        elif isinstance(activity, CustomActivity):
            presences.append(
                {
                    "name": activity.name,
                    "type": activity.type,
                    "created_at": activity.created_at.strftime("%m/%d/%Y %H:%M:%S %p"),
                    "expires": activity.expires_at.strftime("%m/%d/%Y %H:%M:%S %p")
                    if activity.expires_at
                    else None,
                    "emoji": {
                        "id": activity.emoji.id,
                        "name": activity.emoji.name,
                        "animated": activity.emoji.animated,
                        "url": activity.emoji.url,
                    }
                    if activity.emoji
                    else None,
                }
            )
        elif isinstance(activity, Game):
            presences.append(
                {
                    "name": activity.name,
                    "type": activity.type,
                    "time": {
                        "start": activity.start.strftime("%m/%d/%Y %H:%M:%S %p"),
                        "end": activity.end.strftime("%m/%d/%Y %H:%M:%S %p")
                        if activity.end
                        else None,
                    },
                }
            )
    return presences
