// 🔧 CONFIG: Your deployed backend URL
const API_BASE = 'https://youtube-6t33.onrender.com';

// Helper: Get element by ID
const $ = id => document.getElementById(id);

// ========================================
// 📋 Clipboard Functions
// ========================================
$('pasteBtn').addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    $('url').value = text.trim();
    $('url').focus();
    showResult('✅', 'URL pasted from clipboard!');
    setTimeout(() => $('resultBox').classList.remove('show'), 2500);
  } catch (e) {
    showResult('❌', 'Clipboard access denied. Please paste manually (Ctrl+V / Cmd+V)');
  }
});

$('clearBtn').addEventListener('click', () => {
  $('url').value = '';
  $('previewSection').style.display = 'none';
  $('resultBox').classList.remove('show');
  $('url').focus();
});

// ========================================
// 🔍 Validation
// ========================================
const isValidYouTubeURL = (url) => {
  const patterns = [
    /^(https?:\/\/)?(www\.)?youtube\.com\/watch\?v=[\w-]+/,
    /^(https?:\/\/)?(www\.)?youtube\.com\/shorts\/[\w-]+/,
    /^(https?:\/\/)?(www\.)?youtube\.com\/playlist\?list=[\w-]+/,
    /^(https?:\/\/)?youtu\.be\/[\w-]+/
  ];
  return patterns.some(pattern => pattern.test(url.trim()));
};

// ========================================
// 📹 Fetch Video Info
// ========================================
$('fetchInfoBtn').addEventListener('click', async () => {
  const url = $('url').value.trim();
  
  if (!url) {
    showResult('❌', 'Please enter a YouTube URL');
    return;
  }
  
  if (!isValidYouTubeURL(url)) {
    showResult('❌', 'Invalid YouTube URL. Please check and try again.');
    return;
  }

  setLoading(true);
  $('previewSection').style.display = 'none';
  
  try {
    const response = await fetch(`${API_BASE}/api/info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || `API Error: ${response.status}`);
    }
    
    // Show video preview section
    $('previewSection').style.display = 'block';
    
    // Update video player & info
    const videoPlayer = $('videoPlayer');
    videoPlayer.poster = data.thumbnail || '';
    videoPlayer.title = data.title || 'Video Preview';
    
    $('videoTitle').textContent = data.title || 'Unknown Title';
    $('videoMeta').innerHTML = `
      ⏱️ Duration: ${formatDuration(data.duration)} • 
      👤 Channel: ${data.uploader || 'Unknown'} • 
      🆔 ${data.id || ''}
    `;
    
    showResult('✅', '✅ Video info loaded successfully!');
    
  } catch (error) {
    console.error('Fetch info error:', error);
    showResult('❌', `Error: ${error.message}`);
  } finally {
    setLoading(false);
  }
});

// ========================================
// 🚀 Convert & Download
// ========================================
$('downloadBtn').addEventListener('click', async () => {
  const url = $('url').value.trim();
  const format = $('format').value;
  const quality = $('quality').value;
  
  if (!url) {
    showResult('❌', 'Please enter a YouTube URL');
    return;
  }
  
  if (!isValidYouTubeURL(url)) {
    showResult('❌', 'Invalid YouTube URL');
    return;
  }

  setLoading(true);
  
  try {
    const response = await fetch(`${API_BASE}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        url, 
        format, 
        quality,
        timestamp: Date.now() // Prevent caching
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.detail || `Download failed: ${response.status}`);
    }
    
    if (!data.downloadUrl) {
      throw new Error('No download URL received from server');
    }
    
    // Show download link
    const downloadLink = data.downloadUrl;
    const fileExt = format === 'mp3' ? 'mp3' : 'mp4';
    const safeTitle = (data.title || 'video').replace(/[^a-z0-9]/gi, '_').substring(0, 50);
    
    showResult('✅', `
      <strong>🎬 ${data.title || 'Video'}</strong><br><br>
      ✅ Your file is ready!<br>
      <a href="${downloadLink}" target="_blank" style="color:var(--primary);font-weight:bold;text-decoration:none">
        ⬇️ Click Here to Download
      </a><br><br>
      <small style="color:var(--text-dim)">
        💡 Tip: Right-click the link → "Save link as..." for best results.<br>
        🔗 Link expires in ~6 hours. Refresh if needed.
      </small>
    `);
    
    // Optional: Auto-open download (may be blocked by popup blocker)
    // window.open(downloadLink, '_blank');
    
  } catch (error) {
    console.error('Download error:', error);
    showResult('❌', `❌ ${error.message}`);
  } finally {
    setLoading(false);
  }
});

// ========================================
// 🎨 UI Helper Functions
// ========================================
function setLoading(isLoading) {
  const btn = $('downloadBtn');
  btn.disabled = isLoading;
  btn.innerHTML = isLoading 
    ? '<span style="display:inline-block;width:16px;height:16px;border:2px solid rgba(255,255,255,0.3);border-top-color:white;border-radius:50%;animation:spin 0.8s linear infinite;margin-right:8px;vertical-align:middle"></span>Processing...' 
    : '🚀 Convert & Download';
}

function showResult(status, htmlContent) {
  const statusEl = $('resultStatus');
  const contentEl = $('resultContent');
  
  statusEl.textContent = status;
  statusEl.style.color = status.includes('✅') ? 'var(--success)' : 'var(--error)';
  contentEl.innerHTML = htmlContent;
  
  $('resultBox').classList.add('show');
}

// Close result box
$('closeResult').addEventListener('click', () => {
  $('resultBox').classList.remove('show');
});

// Enter key to trigger download
$('url').addEventListener('keypress', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    $('downloadBtn').click();
  }
});

// Auto-hide result when typing
$('url').addEventListener('input', () => {
  if ($('resultBox').classList.contains('show')) {
    $('resultBox').classList.remove('show');
  }
});

// Format seconds to MM:SS
function formatDuration(seconds) {
  if (!seconds || typeof seconds !== 'number') return '--:--';
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Add CSS animation for loader (if not in style.css)
if (!document.querySelector('#loader-anim')) {
  const style = document.createElement('style');
  style.id = 'loader-anim';
  style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
  document.head.appendChild(style);
}

// Console log for debugging
console.log('🎬 YT Downloader v1.0 Loaded');
console.log('🔗 API Base:', API_BASE);
console.log('💡 Press F12 → Console for debugging');
