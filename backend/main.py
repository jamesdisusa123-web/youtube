from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import yt_dlp
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="YT Downloader API", version="1.2.0")

# 🔒 CORS for your GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jamesdisusa123-web.github.io", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===========================
# 📦 Models
# ===========================
class InfoRequest(BaseModel):
    url: str = Field(..., min_length=10)

class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=10)
    format: str = Field(default="mp4", pattern="^(mp4|mp3)$")
    quality: str = Field(default="best", pattern="^(best|1080|720|480)$")
    playlist_index: Optional[int] = Field(default=None, ge=1)

# ===========================
# ⚙️ Helpers
# ===========================
def is_playlist(url: str) -> bool:
    return "playlist?list=" in url or "/playlist" in url

def get_opts(fmt: str, quality: str, playlist: bool = False) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist" if playlist else False,
        "socket_timeout": 30,
        "retries": 2,
        "no_check_certificate": True,
    }
    if fmt == "mp3":
        # For MP3, we'll return the best audio stream URL (no server-side conversion)
        opts["format"] = "bestaudio/best"
    else:
        if quality == "best":
            opts["format"] = "bestvideo+bestaudio/best"
        else:
            opts["format"] = f"best[height<={quality}]/best"
    return opts

def safe_extract_info(url: str, opts: dict) -> dict:
    """Extract info with error handling"""
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)

# ===========================
# 🌐 Endpoints
# ===========================

@app.get("/")
def health():
    return {"status": "✅ OK", "version": "1.2.0", "ffmpeg": "installed"}

@app.post("/api/info")
async def get_info(req: InfoRequest):
    url = req.url.strip()
    logger.info(f"ℹ️  Info request: {url}")
    
    try:
        opts = get_opts("mp4", "best", playlist=is_playlist(url))
        info = safe_extract_info(url, opts)
        
        if is_playlist(url):
            # Playlist response
            entries = [e for e in info.get("entries", []) if e and isinstance(e, dict)][:20]
            return {
                "type": "playlist",
                "title": info.get("title", "Playlist"),
                "video_count": len(entries),
                "videos": [{
                    "id": e.get("id"),
                    "title": e.get("title", "Unknown"),
                    "thumbnail": e.get("thumbnail") or "",
                    "duration": e.get("duration", 0),
                    "url": e.get("webpage_url") or e.get("url", "")
                } for e in entries]
            }
        else:
            # Single video
            return {
                "type": "video",
                "id": info.get("id"),
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail") or "",
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader") or info.get("channel", "Unknown"),
                "url": info.get("webpage_url") or info.get("url", "")
            }
            
    except Exception as e:
        logger.error(f"Info error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch info: {str(e)[:150]}")

@app.post("/api/download")
async def download(req: DownloadRequest):
    url = req.url.strip()
    fmt = req.format
    quality = req.quality
    idx = req.playlist_index
    
    logger.info(f"⬇️  Download: {url} | {fmt}/{quality} | idx:{idx}")
    
    try:
        # If playlist + specific index, get that video's URL first
        if is_playlist(url) and idx:
            opts = get_opts(fmt, quality, playlist=True)
            info = safe_extract_info(url, opts)
            entries = [e for e in info.get("entries", []) if e]
            if not (0 < idx <= len(entries)):
                raise ValueError(f"Index {idx} out of range (1-{len(entries)})")
            url = entries[idx - 1].get("webpage_url") or entries[idx - 1].get("url")
        
        # Get direct download URL (no server processing)
        opts = get_opts(fmt, quality, playlist=False)
        info = safe_extract_info(url, opts)
        
        # Extract best available direct URL
        direct_url = None
        if info.get("url"):
            direct_url = info["url"]
        elif info.get("formats"):
            # Filter formats by quality if specified
            formats = info["formats"]
            if quality != "best" and fmt == "mp4":
                filtered = [f for f in formats if f.get("height", 0) <= int(quality)]
                if filtered:
                    direct_url = filtered[-1].get("url")
            if not direct_url:
                direct_url = formats[-1].get("url")
        
        if not direct_url:
            raise ValueError("No downloadable URL found")
        
        return {
            "success": True,
            "title": info.get("title", "Video"),
            "downloadUrl": direct_url,
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0),
            "format": fmt,
            "note": "Link expires in ~6 hours. Use promptly."
        }
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)[:150]}")

@app.options("/api/{path:path}")
async def options():
    return JSONResponse(content={}, status_code=200)
