import hashlib
import secrets
import httpx
import xmltodict
from urllib.parse import urlencode
from app.core.config import settings 


def _checksum(call: str, params: dict) -> str:
    query = urlencode(params)
    raw = f"{call}{query}{settings.BBB_SECRET}"
    return hashlib.sha1(raw.encode()).hexdigest()


async def create_bbb_meeting(
    meeting_id: str,
    title: str,
    attendee_pw: str,
    moderator_pw: str,
    record: bool = False,
) -> dict:
    params = {
        "meetingID": meeting_id,
        "name": title,
        "attendeePW": attendee_pw,
        "moderatorPW": moderator_pw,
        "record": "true" if record else "false",
        "autoStartRecording": "false",
        "allowStartStopRecording": "false",
    }
    params["checksum"] = _checksum("create", params)

    async with httpx.AsyncClient() as client:
        r = await client.get(f"{settings.BBB_URL}/create", params=params)

    result = xmltodict.parse(r.text)["response"]
    if result["returncode"] != "SUCCESS":
        raise Exception(f"BBB create failed: {result.get('message')}")
    return result


def get_join_url(
    meeting_id: str,
    full_name: str,
    password: str,   
    user_id: str,
    logout_url: str = "http://localhost:3000",
    is_moderator: bool = False
) -> str:
    params = {
        "meetingID": meeting_id,
        "fullName": full_name,
        "password": password,
        "userID": user_id,
        "logoutURL": logout_url,
        "role": "MODERATOR" if is_moderator else "VIEWER",
    }
    checksum = _checksum("join", params)
    return f"{settings.BBB_URL}/join?{urlencode(params)}&checksum={checksum}"


async def end_bbb_meeting(meeting_id: str, moderator_pw: str) -> None:
    params = {"meetingID": meeting_id, "password": moderator_pw}
    params["checksum"] = _checksum("end", params)
    async with httpx.AsyncClient() as client:
        await client.get(f"{settings.BBB_URL}/end", params=params)


# async def get_recording(meeting_id: str) -> str | None:
#     params = {"meetingId": meeting_id}
#     params["checksum"] = _checksum("getRecordings", params)

#     try:
#         async with httpx.AsyncClient(timeout=BBB_TIMEOUT) as client:
#             r = await client.get(f"{settings.BBB_URL}/getRecordings", params=params)
#     except httpx.TimeoutException:
#         return None
    
#     if r.status_code != 200:
#         return None
    
#     parsed = xmltodict.parse(r.text)



async def is_meeting_running(meeting_id: str) -> bool:
    params = {"meetingID": meeting_id}
    params["checksum"] = _checksum("isMeetingRunning", params)

    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{settings.BBB_URL}/isMeetingRunning",
            params=params
        )

    result = xmltodict.parse(r.text)["response"]
    return result.get("running") == "true"