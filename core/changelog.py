<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BeamSkin Studio</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --bg: #05070a;
            --surface: #0f1218;
            --accent: #FF6600;
            --accent-glow: rgba(255, 102, 0, 0.6);
            --linux: #f39c12;
            --linux-glow: rgba(243, 156, 18, 0.4);
            --text: #ffffff;
            --text-mute: #94a3b8;
        }

        body {
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Segoe UI', sans-serif;
            margin: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .container {
            width: 100%;
            max-width: 1000px;
            padding: 0px 20px;
            text-align: center;
        }

        .logo { 
            width: 200px;
            margin: 10px 0; 
            filter: drop-shadow(0 0 15px var(--accent-glow)); 
        }

        .display-wrapper {
            width: 100%;
            border-radius: 12px;
            border: 2px solid var(--accent);
            box-shadow: 0 0 30px var(--accent-glow);
            overflow: hidden;
            margin-bottom: 15px;
            background: #000;
            aspect-ratio: 16 / 9;
            position: relative;
        }

        .display-content {
            width: 100%;
            height: 100%;
            position: absolute;
            top: 0;
            left: 0;
            display: none; 
            object-fit: contain;
        }

        .active-content { display: block; }
        .aspect-ratio { width: 100%; height: 100%; background: #000; }
        .aspect-ratio iframe { width: 100%; height: 100%; border: 0; display: block; }

        .gallery-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            width: 100%;
            margin-bottom: 15px;
        }

        .nav-card {
            background: var(--surface);
            border-radius: 8px;
            border: 1px solid #222;
            overflow: hidden;
            cursor: pointer;
            transition: 0.2s;
            position: relative;
        }

        .nav-card img { width: 100%; height: 85px; object-fit: cover; opacity: 0.5; transition: 0.3s; pointer-events: none; }
        .nav-card:hover { border-color: var(--accent); box-shadow: 0 0 15px var(--accent-glow); }
        .nav-card:active { transform: scale(0.95); }
        .nav-card:hover img { opacity: 1; }
        
        .nav-card span {
            position: absolute; bottom: 4px; width: 100%; font-size: 9px; 
            font-weight: 900; color: var(--accent); text-align: center;
            pointer-events: none; text-shadow: 0 1px 3px #000;
        }

        .download-row {
            display: flex;
            justify-content: center;
            gap: 15px;
            width: 100%;
        }

        .dl-btn {
            flex: 1;
            max-width: 450px;
            padding: 12px;
            border-radius: 10px;
            text-decoration: none;
            color: #000 !important;
            font-weight: 900;
            display: flex;
            flex-direction: column;
            align-items: center;
            transition: 0.3s;
            cursor: pointer;
            border: none;
        }

        .dl-btn span,
        .dl-btn .ver-tag {
            color: #000 !important;
        }

        .btn-win { background: var(--accent); box-shadow: 0 0 20px var(--accent-glow); }
        .btn-linux { background: var(--linux); box-shadow: 0 0 20px var(--linux-glow); }
        .dl-btn:hover { transform: translateY(-3px); filter: brightness(1.2); }

        .ver-tag { font-size: 13px; text-transform: uppercase; margin-top: 2px; opacity: 0.9; }
        .count-tag { font-size: 11px; font-weight: 400; margin-top: 2px; opacity: 0.8; }
        .count-tag i { font-size: 9px; }
        
        .dl-btn i { margin-bottom: 2px; font-size: 0.75rem; }

        /* ── Changelog ─────────────────────────────────────────────────────── */
        .changelog-box {
            width: 100%;
            box-sizing: border-box;
            margin-top: 15px;
            padding: 14px 16px;
            border-radius: 8px;
            border: 1px solid #222;
            border-left: 4px solid var(--accent);
            background: var(--surface);
            text-align: left;
            font-size: 0.82rem;
            line-height: 1.7;
        }
        .changelog-box .cl-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 10px;
        }
        .changelog-box .cl-version {
            font-weight: 900; color: var(--accent); font-size: 0.9rem;
        }
        .changelog-box .cl-date {
            color: var(--text-mute); font-size: 0.75rem;
        }
        .changelog-box .cl-title {
            font-weight: 800; color: var(--text); font-size: 0.85rem;
            margin-top: 8px; margin-bottom: 2px;
        }
        .changelog-box .cl-subtitle {
            font-weight: 700; color: var(--accent); font-size: 0.78rem;
            margin-top: 5px;
        }
        .changelog-box .cl-item {
            color: var(--text-mute); padding-left: 12px;
        }
        .changelog-box .cl-item::before {
            content: "• "; color: var(--accent);
        }
        .changelog-box .cl-note {
            font-style: italic; color: var(--text-mute); font-size: 0.75rem;
            margin-top: 4px;
        }
        .changelog-box .cl-separator {
            border: none; border-top: 1px solid #222;
            margin: 8px 0;
        }

        .footer { margin-top: 20px; color: var(--text-mute); font-size: 0.8rem; padding-bottom: 15px; }
        .footer a { color: var(--accent); text-decoration: none; font-weight: bold; }

        @media (max-width: 800px) { .gallery-grid { grid-template-columns: repeat(2, 1fr); } }
    </style>
</head>
<body>

<div class="container">
    <img src="beamSkin_studio_logo.png" alt="BeamSkin Studio" class="logo">

    <div id="displayBox" class="display-wrapper">
        <div id="videoContainer" class="display-content active-content">
            <div class="aspect-ratio">
                <iframe src="https://www.youtube.com/embed/N1M8Tsnlodw" allowfullscreen></iframe>
            </div>
        </div>
        <img id="imageDisplay" class="display-content" src="" alt="Screenshot">
    </div>

    <div class="gallery-grid">
        <div class="nav-card" onclick="showVideo()">
            <img src="https://img.youtube.com/vi/N1M8Tsnlodw/0.jpg">
            <span>PREVIEW VIDEO</span>
        </div>
        <div class="nav-card" onclick="showImage('image1.png')"><img src="image1.png"><span>UI PREVIEW</span></div>
        <div class="nav-card" onclick="showImage('image2.png')"><img src="image2.png"><span>USER GUIDE</span></div>
        <div class="nav-card" onclick="showImage('image3.png')"><img src="image3.png"><span>CAR DATABASE</span></div>
        <div class="nav-card" onclick="showImage('image4.png')"><img src="image4.png"><span>MOD TOOLS</span></div>
        <div class="nav-card" onclick="showImage('image5.png')"><img src="image5.png"><span>APP SETTINGS</span></div>
        <div class="nav-card" onclick="showImage('image6.png')"><img src="image6.png"><span>VERSION INFO</span></div>
        <div class="nav-card" onclick="window.open('https://github.com/BeamSkin-Studio', '_blank')">
            <img src="https://opengraph.githubassets.com/1/BeamSkin-Studio">
            <span>VIEW SOURCE</span>
        </div>
    </div>

    <div style="
        width: 100%;
        box-sizing: border-box;
        margin-bottom: 15px;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #f39c12;
        border-left: 4px solid #f39c12;
        background: rgba(243, 156, 18, 0.07);
        text-align: left;
        font-size: 0.82rem;
        color: var(--text-mute);
        line-height: 1.6;
    ">
        <div style="font-weight: 700; color: #f39c12; margin-bottom: 5px; font-size: 0.88rem;">
            <i class="fas fa-triangle-exclamation"></i> WORK IN PROGRESS — READ BEFORE USING
        </div>
        BeamSkin Studio is <strong style="color: var(--text);">usable but still in active development</strong> — crashes are rare, but bugs are possible.<br><br>
        <strong style="color: var(--text);">Current known limitations:</strong><br>
        • <strong style="color: var(--text);">Game updates</strong> may rename textures, causing some skins to break until a fix is released.<br>
        • <strong style="color: var(--text);">Vehicle variants</strong> (box trucks, ambulances, etc.) are not currently supported.<br>
        • <strong style="color: var(--text);">Mod support</strong> is present but limited — not all mods will work correctly.<br>
        • Some features are still <strong style="color: var(--text);">missing or incomplete</strong>.<br><br>
        <span style="font-style: italic;">The tool is actively being improved — if something breaks, check back for updates.</span>
    </div>

    <div class="download-row">
        <button id="winBtn" class="dl-btn btn-win">
            <span><i class="fab fa-windows"></i> WINDOWS DOWNLOAD</span>
            <span id="winVer" class="ver-tag">Checking...</span>
            <span id="win-count" class="count-tag"><i class="fas fa-download"></i> Loading...</span>
        </button>
        <button id="linBtn" class="dl-btn btn-linux">
            <span><i class="fab fa-linux"></i> LINUX DOWNLOAD</span>
            <span id="linVer" class="ver-tag">Checking...</span>
            <span id="lin-count" class="count-tag"><i class="fas fa-download"></i> Loading...</span>
        </button>
    </div>

    <div style="margin-top: 10px; font-size: 0.8rem; color: var(--text-mute); text-align: center;">
        <i class="fas fa-download" style="color: var(--accent); font-size: 0.7rem;"></i>
        All-time downloads: <span id="grand-total" style="color: var(--text); font-weight: 600;">Loading...</span>
    </div>

    <div id="changelogBox" class="changelog-box">
        <div class="cl-header">
            <span class="cl-version">📋 Latest Changelog</span>
            <span id="clDate" class="cl-date">Loading...</span>
        </div>
        <div id="clEntries">Loading changelog...</div>
    </div>

    <div class="footer">
        Project made by <a href="https://linktr.ee/burzt_yt" target="_blank">@Burzt_YT</a>
    </div>
</div>

<script>
    const winRepo = "BeamSkin-Studio/BeamSkin-Studio-Beta";
    const linuxRepo = "BeamSkin-Studio/BeamSkin-Studio-Linux-Beta";
    
    let winUrl = "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Beta/releases/latest";
    let linuxUrl = "https://github.com/BeamSkin-Studio/BeamSkin-Studio-Linux-Beta/releases/latest";

    async function getRepoData(repo, labelId) {
        try {
            const response = await fetch(`https://api.github.com/repos/${repo}/releases`);
            
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const releases = await response.json();
            let totalDownloads = 0;
            let latestDownloads = 0;
            let latestAssetUrl = `https://github.com/${repo}/releases/latest`;

            releases.forEach((release, index) => {
                release.assets.forEach(asset => {
                    totalDownloads += asset.download_count;
                    if (index === 0) latestDownloads += asset.download_count;
                });
            });

            if (releases.length > 0) {
                const latest = releases[0];
                document.getElementById(labelId).innerText = latest.tag_name;
                if (latest.assets && latest.assets.length > 0) {
                    latestAssetUrl = latest.assets[0].browser_download_url;
                }
            }

            return { url: latestAssetUrl, latest: latestDownloads, total: totalDownloads };
            
        } catch (err) {
            console.error(`Error: ${err.message}`);
            document.getElementById(labelId).innerText = "Latest Release";
            return { url: `https://github.com/${repo}/releases/latest`, latest: 0, total: 0 };
        }
    }

    async function init() {
        try {
            const [winData, linuxData] = await Promise.all([
                getRepoData(winRepo, 'winVer'),
                getRepoData(linuxRepo, 'linVer')
            ]);
            
            winUrl = winData.url;
            linuxUrl = linuxData.url;

            document.getElementById('win-count').innerHTML = '<i class="fas fa-download"></i> ' + winData.latest.toLocaleString() + ' downloads (latest)';
            document.getElementById('lin-count').innerHTML = '<i class="fas fa-download"></i> ' + linuxData.latest.toLocaleString() + ' downloads (latest)';

            const grandTotal = winData.total + linuxData.total;
            document.getElementById('grand-total').innerText = grandTotal.toLocaleString();

        } catch (err) {
            console.error('Init error:', err);
            document.getElementById('win-count').innerHTML = '<i class="fas fa-download"></i> Unavailable';
            document.getElementById('lin-count').innerHTML = '<i class="fas fa-download"></i> Unavailable';
            document.getElementById('grand-total').innerText = 'Unavailable';
        }
    }

    document.getElementById('winBtn').addEventListener('click', () => {
        window.location.href = winUrl;
    });
    
    document.getElementById('linBtn').addEventListener('click', () => {
        window.location.href = linuxUrl;
    });

    const videoContainer = document.getElementById('videoContainer');
    const imageDisplay = document.getElementById('imageDisplay');

    function showImage(src) {
        videoContainer.style.display = 'none';
        imageDisplay.src = src;
        imageDisplay.style.display = 'block';
    }

    function showVideo() {
        imageDisplay.style.display = 'none';
        videoContainer.style.display = 'block';
    }

    async function fetchChangelog() {
        try {
            const res = await fetch('https://raw.githubusercontent.com/BeamSkin-Studio/BeamSkin-Studio-Beta/main/core/changelog.py');
            if (!res.ok) throw new Error('Failed to fetch');
            const text = await res.text();

            // Find start of CHANGELOGS list
            const listStart = text.indexOf('CHANGELOGS = [');
            if (listStart === -1) throw new Error('No CHANGELOGS found');

            // Extract the first { ... } block (first/latest version entry)
            const content = text.slice(listStart);
            let depth = 0, start = -1, end = -1;
            for (let i = 0; i < content.length; i++) {
                if (content[i] === '{') { if (depth === 0) start = i; depth++; }
                else if (content[i] === '}') { depth--; if (depth === 0) { end = i; break; } }
            }
            if (start === -1 || end === -1) throw new Error('Could not parse entry');

            const block = content.slice(start, end + 1);

            const version = (block.match(/"version":\s*"([^"]+)"/) || [])[1] || '?';
            const date    = (block.match(/"date":\s*"([^"]+)"/)    || [])[1] || '';

            // Parse all entry calls: title("..."), item("..."), separator(), etc.
            const entries = [];
            const re = /(title|subtitle|item|note|separator)\((?:"((?:[^"\\]|\\.)*)")?\)/g;
            let m;
            while ((m = re.exec(block)) !== null) {
                entries.push({ type: m[1], text: m[2] || '' });
            }

            document.getElementById('clDate').textContent = `v${version}  •  ${date}`;

            const container = document.getElementById('clEntries');
            container.innerHTML = '';
            for (const entry of entries) {
                if (entry.type === 'title') {
                    const el = document.createElement('div');
                    el.className = 'cl-title'; el.textContent = entry.text;
                    container.appendChild(el);
                } else if (entry.type === 'subtitle') {
                    const el = document.createElement('div');
                    el.className = 'cl-subtitle'; el.textContent = entry.text;
                    container.appendChild(el);
                } else if (entry.type === 'item') {
                    const el = document.createElement('div');
                    el.className = 'cl-item'; el.textContent = entry.text;
                    container.appendChild(el);
                } else if (entry.type === 'note') {
                    const el = document.createElement('div');
                    el.className = 'cl-note'; el.textContent = '💡 ' + entry.text;
                    container.appendChild(el);
                } else if (entry.type === 'separator') {
                    const el = document.createElement('hr');
                    el.className = 'cl-separator';
                    container.appendChild(el);
                }
            }
        } catch (err) {
            console.error('Changelog error:', err);
            document.getElementById('clEntries').textContent = 'Could not load changelog.';
            document.getElementById('clDate').textContent = '';
        }
    }

    init();
    fetchChangelog();
</script>

</body>
</html>
