
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import re

app = FastAPI(title="YT Downloader API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔒 Replace with your GitHub Pages URL in production
    allow_methods=["*"],
    allow_headers=["*"],
)

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    format: str
    quality: str

def get_yt_opts(fmt: str, quality: str) -> dict:
    opts = {"quiet": True, "no_warnings": True, "extract_flat": False}
    if fmt == "mp3":
        opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        })
    else:
        if quality == "best":
            opts["format"] = "bestvideo+bestaudio/best"
        else:
            opts["format"] = f"bestvideo[height<={quality}]+bestaudio/best"
    return opts

@app.post("/api/info")
async def get_info(req: InfoRequest):
    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(req.url, download=False)
            return {
                "title": info.get("title", "Unknown"),
                "thumbnail": info.get("thumbnail", ""),
                "duration": info.get("duration", 0),
                "uploader": info.get("uploader", ""),
                "id": info.get("id", "")
            }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid URL or fetch failed: {str(e)}")

@app.post("/api/download")
async def download(req: DownloadRequest):
    try:
        opts = get_yt_opts(req.format, req.quality)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(req.url, download=False)
            
            # Get direct stream URL
            direct_url = info.get("url")
            if not direct_url and "formats" in info:
                # Fallback to last format's url
                direct_url = info["formats"][-1].get("url")
                
            if not direct_url:
                raise ValueError("Could not extract download link")
                
            return {
                "success": True,
                "title": info.get("title", "video"),
                "downloadUrl": direct_url
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")

@app.get("/")
def root():
    return {"status": "✅ API Running", "docs": "/docs"}
