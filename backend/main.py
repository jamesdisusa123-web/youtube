from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import yt_dlp
import re
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YT Downloader API",
    description="YouTube video & playlist downloader powered by yt-dlp",
    version="1.1.0"
)

# 🔒 CORS: Allow your GitHub Pages + all for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://jamesdisusa123-web.github.io", "*"],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# ===========================
# 📦 Request Models
# ===========================
class InfoRequest(BaseModel):
    url: str = Field(..., min_length=10, description="YouTube video or playlist URL")

class DownloadRequest(BaseModel):
    url: str = Field(..., min_length=10)
    format: str = Field(default="mp4", pattern="^(mp4|mp3)$")
    quality: str = Field(default="best", pattern="^(best|1080|720|480|320kbps|192kbps)$")
    playlist_index: Optional[int] = Field(default=None, description="Download specific video from playlist (1-based)")

# ===========================
# ⚙️ yt-dlp Helper Functions
# ===========================
def is_playlist_url(url: str) -> bool:
    """Check if URL is a YouTube playlist"""
    return any(pattern in url for pattern in [
        "playlist?list=", "youtube.com/playlist", "youtu.be/playlist"
    ])

def get_ydl_opts(fmt: str, quality: str, playlist: bool = False) -> dict:
    """Generate yt-dlp options based on format/quality"""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist" if playlist else False,
        "socket_timeout": 30,
        "retries": 3,
    }
    
    if fmt == "mp3":
        audio_quality = quality.replace("kbps", "") if "kbps" in quality else "192"
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_quality,
            }],
        })
    else:
        # Video format selection
        if quality == "best":
            opts["format"] = "bestvideo+bestaudio/best"
        else:
            opts["format"] = f"bestvideo[height<={quality}]+bestaudio/best[height<={quality}]"
    
    return opts

def extract_video_info(info: dict) -> dict:
    """Extract clean video info from yt-dlp response"""
    return {
        "id": info.get("id", ""),
        "title": info.get("title", "Unknown"),
        "thumbnail": info.get("thumbnail") or info.get("thumbnails", [{}])[-1].get("url", ""),
        "duration": info.get("duration", 0),
        "uploader": info.get("uploader") or info.get("channel", "Unknown"),
        "view_count": info.get("view_count", 0),
        "upload_date": info.get("upload_date", ""),
        "description": (info.get("description") or "")[:200] + "..." if info.get("description") else "",
        "url": info.get("webpage_url") or info.get("url", ""),
    }

# ===========================
# 🌐 API Endpoints
# ===========================

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "✅ API Running",
        "version": "1.1.0",
        "endpoints": {
            "info": "POST /api/info",
            "download": "POST /api/download"
        },
        "docs": "/docs"
    }

@app.post("/api/info")
async def get_video_info(req: InfoRequest):
    """
    Fetch video/playlist info without downloading.
    Returns single video info OR playlist with video list.
    """
    url = req.url.strip()
    logger.info(f"🔍 Fetching info for: {url}")
    
    try:
        if is_playlist_url(url):
            # 🎵 Handle Playlist
            opts = get_ydl_opts("mp4", "best", playlist=True)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info or "entries" not in info:
                    raise ValueError("Could not extract playlist info")
                
                # Extract playlist metadata
                playlist_info = {
                    "type": "playlist",
                    "id": info.get("id", ""),
                    "title": info.get("title", "Untitled Playlist"),
                    "uploader": info.get("uploader") or info.get("channel", "Unknown"),
                    "thumbnail": info.get("thumbnail") or (info.get("entries", [{}])[0].get("thumbnail") if info.get("entries") else ""),
                    "video_count": info.get("count") or len([e for e in info.get("entries", []) if e]),
                    "videos": []
                }
                
                # Extract first 20 videos (to avoid huge responses)
                entries = [e for e in info.get("entries", []) if e and isinstance(e, dict)][:20]
                for entry in entries:
                    playlist_info["videos"].append(extract_video_info(entry))
                
                return JSONResponse(content=playlist_info)
        
        else:
            # 🎬 Handle Single Video
            opts = get_ydl_opts("mp4", "best", playlist=False)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("Could not extract video info")
                
                video_info = extract_video_info(info)
                video_info["type"] = "video"
                
                return JSONResponse(content=video_info)
                
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"yt-dlp error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid URL or video unavailable: {str(e)[:100]}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)[:100]}")

@app.post("/api/download")
async def download_video(req: DownloadRequest):
    """
    Generate direct download URL(s) for video or playlist.
    For playlists: returns array of download links.
    """
    url = req.url.strip()
    fmt = req.format
    quality = req.quality
    playlist_idx = req.playlist_index  # 1-based index for single video from playlist
    
    logger.info(f"🚀 Download request: {url} | {fmt}/{quality} | idx:{playlist_idx}")
    
    try:
        if is_playlist_url(url) and playlist_idx is None:
            # 🎵 Download Entire Playlist (return list of URLs)
            opts = get_ydl_opts(fmt, quality, playlist=True)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info or "entries" not in info:
                    raise ValueError("Could not process playlist")
                
                entries = [e for e in info.get("entries", []) if e and isinstance(e, dict)]
                if not entries:
                    raise ValueError("Playlist is empty")
                
                results = []
                for i, entry in enumerate(entries[:10], 1):  # Limit to 10 videos for free tier
                    try:
                        # Get direct URL for each video
                        direct_url = entry.get("url") or (entry.get("formats", [{}])[-1].get("url") if entry.get("formats") else None)
                        if not direct_url:
                            # Fallback: re-extract with fresh opts
                            single_opts = get_ydl_opts(fmt, quality, playlist=False)
                            with yt_dlp.YoutubeDL(single_opts) as single_ydl:
                                single_info = single_ydl.extract_info(entry.get("url") or entry.get("webpage_url"), download=False)
                                direct_url = single_info.get("url") or single_info["formats"][-1].get("url")
                        
                        if direct_url:
                            results.append({
                                "index": i,
                                "title": entry.get("title", f"Video {i}"),
                                "downloadUrl": direct_url,
                                "thumbnail": entry.get("thumbnail", ""),
                                "duration": entry.get("duration", 0)
                            })
                    except Exception as e:
                        logger.warning(f"Failed to process video {i}: {str(e)}")
                        continue
                
                if not results:
                    raise ValueError("Could not generate any download links")
                
                return JSONResponse(content={
                    "type": "playlist",
                    "playlist_title": info.get("title", "Playlist"),
                    "total_videos": len(results),
                    "format": fmt,
                    "quality": quality,
                    "downloads": results,
                    "note": "Links expire in ~6 hours. Download promptly."
                })
        
        else:
            # 🎬 Single Video Download (or specific playlist video)
            target_url = url
            
            # If playlist + index provided, get that specific video URL first
            if is_playlist_url(url) and playlist_idx and playlist_idx > 0:
                opts = get_ydl_opts(fmt, quality, playlist=True)
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    entries = [e for e in info.get("entries", []) if e]
                    if 0 < playlist_idx <= len(entries):
                        target_url = entries[playlist_idx - 1].get("webpage_url") or entries[playlist_idx - 1].get("url")
                    else:
                        raise ValueError(f"Playlist index {playlist_idx} out of range (1-{len(entries)})")
            
            # Generate download URL for single video
            opts = get_ydl_opts(fmt, quality, playlist=False)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target_url, download=False)
                
                if not info:
                    raise ValueError("Could not extract video")
                
                # Get direct stream URL
                direct_url = info.get("url")
                if not direct_url and info.get("formats"):
                    direct_url = info["formats"][-1].get("url")
                
                if not direct_url:
                    raise ValueError("No downloadable URL found")
                
                return JSONResponse(content={
                    "type": "video",
                    "title": info.get("title", "Video"),
                    "downloadUrl": direct_url,
                    "thumbnail": info.get("thumbnail", ""),
                    "duration": info.get("duration", 0),
                    "format": fmt,
                    "quality": quality,
                    "note": "Link expires in ~6 hours"
                })
                
    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)[:100]}")
    except Exception as e:
        logger.error(f"Unexpected download error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)[:100]}")

# ===========================
# 🔧 Utility Endpoints (Optional)
# ===========================

@app.options("/api/{path:path}")
async def preflight_handler(path: str):
    """Handle CORS preflight requests"""
    return JSONResponse(content={}, status_code=200)

@app.get("/api/test")
async def test_endpoint():
    """Simple test endpoint to verify API is working"""
    return {"message": "✅ API is healthy", "timestamp": time.time()}

# ===========================
# 🚀 Run with: uvicorn main:app --host 0.0.0.0 --port $PORT
# ===========================
