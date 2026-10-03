import asyncio
import socket
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import aiohttp

app = FastAPI(title="SleepyByte Unified Reconnaissance Engine")
templates = Jinja2Templates(directory="templates")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Accept-Language": "en-US,en;q=0.5"
}

DISCORD_EPOCH = 1420070400000

def parse_discord_id(user_id: str):
    if not user_id.isdigit():
        return None
    uid = int(user_id)
    timestamp_ms = (uid >> 22) + DISCORD_EPOCH
    creation_date = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
    return {
        "user_id": user_id,
        "created_at_utc": creation_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "timestamp_ms": timestamp_ms
    }

async def resolve_server_ips(url: str):
    try:
        hostname = urlparse(url).netloc or url
        loop = asyncio.get_event_loop()
        addr_info = await loop.getaddrinfo(hostname, None, socket.AF_INET)
        ips = sorted(list(set([info[4][0] for info in addr_info])))
        
        for ip in ips:
            if any(c in hostname.lower() for c in ["discord", "github", "twitch", "x.com", "roblox"]):
                return [f"{ip} (N/A – Platform CDN / Edge Node)"]
        return ips
    except Exception:
        return ["N/A – Platform CDN / Resolution Blocked"]

async def fetch_wayback_snapshots(session, url):
    archive_url = f"http://archive.org/wayback/available?url={url}"
    try:
        async with session.get(archive_url, headers=HEADERS, timeout=3) as resp:
            if resp.status == 200:
                data = await resp.json()
                snapshots = data.get("archived_snapshots", {})
                if "closest" in snapshots and snapshots["closest"].get("available"):
                    snapshot_info = snapshots["closest"]
                    timestamp = snapshot_info.get("timestamp", "")
                    formatted_date = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}" if len(timestamp) >= 8 else timestamp
                    return {
                        "has_archive": True,
                        "archive_url": snapshot_info.get("url"),
                        "date": formatted_date
                    }
    except Exception:
        pass
    return {"has_archive": False, "archive_url": None, "date": None}

async def fetch_github_data(session, handle):
    url = f"https://api.github.com/users/{handle}"
    target_url = f"https://github.com/{handle}"
    try:
        ips = await resolve_server_ips(target_url)
        async with session.get(url, headers=HEADERS, timeout=5) as resp:
            if resp.status == 200:
                data = await resp.json()
                wayback = await fetch_wayback_snapshots(session, target_url)
                created_at = data.get("created_at", "N/A")
                if created_at != "N/A":
                    created_at = created_at.replace("T", " ").replace("Z", " UTC")
                return {
                    "platform": "GitHub",
                    "status": "Found",
                    "status_code": 200,
                    "url": target_url,
                    "avatar": data.get("avatar_url"),
                    "bio": data.get("bio") or "N/A",
                    "created_at": created_at,
                    "ips": ips,
                    "meta": {
                        "Public Repos": data.get("public_repos"),
                        "Followers": data.get("followers"),
                        "Location": data.get("location") or "N/A"
                    },
                    "wayback": wayback
                }
            return {"platform": "GitHub", "status": "Not Found", "status_code": 404, "url": target_url, "avatar": None, "created_at": None, "ips": ips, "meta": {}, "wayback": None}
    except Exception:
        return {"platform": "GitHub", "status": "Error", "status_code": 500, "url": target_url, "avatar": None, "created_at": None, "ips": [], "meta": {}, "wayback": None}

async def fetch_reddit_data(session, handle):
    url = f"https://www.reddit.com/user/{handle}/about.json"
    target_url = f"https://www.reddit.com/user/{handle}"
    try:
        ips = await resolve_server_ips(target_url)
        async with session.get(url, headers=HEADERS, timeout=5) as resp:
            if resp.status == 200:
                res = await resp.json()
                data = res.get("data", {})
                created_utc = data.get("created_utc")
                created = datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC') if created_utc else "N/A"
                wayback = await fetch_wayback_snapshots(session, target_url)
                avatar = data.get("snoovatar_img") or data.get("icon_img")
                if avatar: avatar = avatar.split("?")[0]
                return {
                    "platform": "Reddit",
                    "status": "Found",
                    "status_code": 200,
                    "url": target_url,
                    "avatar": avatar,
                    "bio": data.get("subreddit", {}).get("public_description", "N/A"),
                    "created_at": created,
                    "ips": ips,
                    "meta": {
                        "Total Karma": data.get("total_karma", 0),
                        "Verified Email": str(data.get("has_verified_email", False))
                    },
                    "wayback": wayback
                }
            return {"platform": "Reddit", "status": "Not Found", "status_code": 404, "url": target_url, "avatar": None, "created_at": None, "ips": ips, "meta": {}, "wayback": None}
    except Exception:
        return {"platform": "Reddit", "status": "Error", "status_code": 500, "url": target_url, "avatar": None, "created_at": None, "ips": [], "meta": {}, "wayback": None}

async def fetch_discord_lookup(session, identifier):
    ips = await resolve_server_ips("https://discord.com")
    is_id = identifier.isdigit()
    snowflake_data = parse_discord_id(identifier) if is_id else None
    target_url = f"https://discord.com/users/{identifier}" if is_id else f"https://discord.gg/{identifier}"
    created_at = snowflake_data["created_at_utc"] if snowflake_data else "Unknown (Handle search)"
    
    wayback = await fetch_wayback_snapshots(session, target_url)
    
    return {
        "platform": "Discord",
        "status": "Found" if is_id else "Evaluated",
        "status_code": 200,
        "url": target_url,
        "avatar": None,
        "bio": "Discord Target Snowflake Analysis",
        "created_at": created_at,
        "ips": ips,
        "meta": {
            "Snowflake ID": identifier if is_id else "N/A",
            "Timestamp MS": snowflake_data["timestamp_ms"] if snowflake_data else "N/A"
        },
        "wayback": wayback,
        "snowflake": snowflake_data
    }

async def check_generic_target(session, platform, url_pattern, handle):
    url = url_pattern.format(handle=handle)
    try:
        ips = await resolve_server_ips(url)
        async with session.get(url, headers=HEADERS, timeout=4, allow_redirects=True) as resp:
            wayback = await fetch_wayback_snapshots(session, url)
            if resp.status == 200:
                return {
                    "platform": platform,
                    "status": "Found",
                    "status_code": 200,
                    "url": url,
                    "avatar": None,
                    "bio": f"Public profile active on {platform}",
                    "created_at": None,
                    "ips": ips,
                    "meta": {"HTTP Status": "200 OK"},
                    "wayback": wayback
                }
            else:
                return {
                    "platform": platform,
                    "status": "Not Found",
                    "status_code": resp.status,
                    "url": url,
                    "avatar": None,
                    "bio": None,
                    "created_at": None,
                    "ips": ips,
                    "meta": {},
                    "wayback": wayback
                }
    except Exception:
        return {
            "platform": platform,
            "status": "Error",
            "status_code": 500,
            "url": url,
            "avatar": None,
            "bio": None,
            "created_at": None,
            "ips": [],
            "meta": {},
            "wayback": None
        }

def generate_ai_analysis(target, results, domain_info=None):
    found_items = [r for r in results if r['status'] == 'Found']
    summary = f"### [AI ANALYST REPORT] Target: {target}\n\n"
    summary += f"- **Impronta Digitale:** Rilevati riscontri positivi su {len(found_items)} piattaforme.\n"
    
    discord_res = next((r for r in results if r['platform'] == 'Discord'), None)
    if discord_res and discord_res.get("snowflake"):
        summary += f"- **Analisi temporale Discord:** Account generato in data {discord_res['created_at']}.\n"
        
    github_res = next((r for r in results if r['platform'] == 'GitHub'), None)
    if github_res and github_res.get("created_at"):
        summary += f"- **Anzianità Developer:** GitHub registrato il {github_res['created_at']}.\n"
        
    summary += "- **Valutazione rischio:** Esposizione moderata/alta per riutilizzo costante dell'handle. Si consiglia pivot su indirizzo IP e verifiche di data breach storiche."
    return summary

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"data": None, "active_tab": "all"})

@app.post("/", response_class=HTMLResponse)
async def scan(
    request: Request, 
    target: str = Form(...), 
    module: str = Form("all"),
    domain: str = Form(None)
):
    search_target = domain if domain else target
    if not search_target:
        return templates.TemplateResponse(request=request, name="index.html", context={"data": None, "active_tab": module})

    generic_targets = [
        ("Telegram", "https://t.me/{handle}"),
        ("X (Twitter)", "https://x.com/{handle}"),
        ("Roblox", "https://www.roblox.com/search/users?keyword={handle}"),
        ("Twitch", "https://www.twitch.tv/{handle}"),
        ("Spotify", "https://open.spotify.com/user/{handle}"),
        ("TikTok", "https://www.tiktok.com/@{handle}"),
        ("Instagram", "https://www.instagram.com/{handle}/"),
        ("Steam", "https://steamcommunity.com/id/{handle}"),
        ("Pinterest", "https://www.pinterest.com/{handle}/"),
        ("SoundCloud", "https://soundcloud.com/{handle}"),
        ("GitLab", "https://gitlab.com/{handle}"),
        ("TryHackMe", "https://tryhackme.com/p/{handle}")
    ]

    results = []
    async with aiohttp.ClientSession() as session:
        if module in ["all", "username", "discord"]:
            discord_res = await fetch_discord_lookup(session, search_target)
            results.append(discord_res)
            
        if module in ["all", "username"]:
            gh_res = await fetch_github_data(session, search_target)
            rd_res = await fetch_reddit_data(session, search_target)
            results.extend([gh_res, rd_res])
            
            tasks = [check_generic_target(session, plat, pat, search_target) for plat, pat in generic_targets]
            generic_results = await asyncio.gather(*tasks)
            results.extend(generic_results)

    ai_report = generate_ai_analysis(search_target, results)
    timestamp_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "data": results,
            "target": search_target,
            "ai_report": ai_report,
            "timestamp_now": timestamp_now,
            "active_tab": module
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
