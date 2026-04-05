
// 🔧 CONFIG: Replace with your deployed backend URL
const API_BASE = ''; // e.g., 'https://your-app.onrender.com'

const $ = id => document.getElementById(id);

// --- Clipboard ---
$('pasteBtn').addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    $('url').value = text.trim();
    $('url').focus();
    showResult('✅', 'Pasted from clipboard');
  } catch (e) {
    showResult('❌', 'Clipboard access denied. Use Ctrl+V');
  }
});

$('clearBtn').addEventListener('click', () => {
  $('url').value = '';
  $('previewSection').style.display = 'none';
  $('resultBox').classList.remove('show');
  $('url').focus();
});

// --- Validation ---
const isValidYT = url => /^(https?:\/\/)?(www\.|m\.)?(youtube\.com|youtu\.be)\/.+/i.test(url.trim());

// --- Fetch Info ---
$('fetchInfoBtn').addEventListener('click', async () => {
  const url = $('url').value.trim();
  if (!url) return showResult('❌', 'Please enter a YouTube URL');
  if (!isValidYT(url)) return showResult('❌', 'Invalid YouTube URL');

  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/info`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Failed to fetch info');

    // Show preview
    $('previewSection').style.display = 'block';
    $('videoPlayer').poster = data.thumbnail || '';
    $('videoPlayer').src = ''; // Preview only, no playback yet
    $('videoTitle').textContent = data.title;
    $('videoMeta').textContent = `Duration: ${formatDuration(data.duration)} • Channel: ${data.uploader || 'Unknown'}`;
    
    showResult('✅', 'Video info loaded successfully!');
  } catch (err) {
    showResult('❌', err.message);
  } finally {
    setLoading(false);
  }
});

// --- Download ---
$('downloadBtn').addEventListener('click', async () => {
  const url = $('url').value.trim();
  const format = $('format').value;
  const quality = $('quality').value;

  if (!url || !isValidYT(url)) return showResult('❌', 'Invalid YouTube URL');

  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/download`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, format, quality })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Download failed');

    const downloadLink = data.downloadUrl;
    showResult('✅', `Ready! <a href="${downloadLink}" target="_blank" style="color:var(--primary);font-weight:bold">⬇️ Click to Download</a>`);
  } catch (err) {
    showResult('❌', err.message);
  } finally {
    setLoading(false);
  }
});

// --- UI Helpers ---
function setLoading(active) {
  $('downloadBtn').disabled = active;
  $('downloadBtn').textContent = active ? '⏳ Processing...' : '🚀 Convert & Download';
}

function showResult(status, html) {
  $('resultStatus').textContent = status;
  $('resultStatus').style.color = status.includes('✅') ? 'var(--success)' : 'var(--error)';
  $('resultContent').innerHTML = html;
  $('resultBox').classList.add('show');
}

$('closeResult').addEventListener('click', () => $('resultBox').classList.remove('show'));
$('url').addEventListener('keypress', e => e.key === 'Enter' && $('downloadBtn').click());

function formatDuration(sec) {
  if (!sec) return '--';
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

console.log('🎬 YT Downloader Loaded | Set API_BASE in js/app.js to enable backend');
