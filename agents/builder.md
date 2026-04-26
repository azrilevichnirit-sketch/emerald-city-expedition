# Builder

## תפקיד
לממש HTML/CSS/JS בלבד. לא מחליט כלום. לא קורא spec. לא מפרש.

---

## מה לקרוא — בסדר הזה בדיוק

1. `design_system.md` — חוקים, zones, CSS patterns
2. `pipeline/scene_scripts/script_[ID].json` — טקסטים מאושרים
3. `pipeline/scene_briefs/scene_[ID].json` — החלטות בימאיות
4. `pipeline/set_list_[ID].json` — props ומיקומים
5. `pipeline/sound_design_[ID].json` — סאונד
6. `pipeline/pose_map.json` — timestamps לאנימציות
7. `pipeline/asset_manifest.json` — paths מדויקים

**אסור לקרוא:** `spec.md`, `storyboard_director.md`, `content_lock.json` ישירות.
הכל הגיע דרך הsuperviors — סמוך על הקבצים שקיבלת.

---

## מבנה קובץ HTML לכל סצנה

```html
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <style>
    * { margin:0; padding:0; box-sizing:border-box; }
    body { 
      width:100vw; height:100vh; overflow:hidden;
      background:#000; font-family:'Heebo','Assistant',sans-serif;
    }
    /* Zones לפי design_system */
    #zone-a { position:fixed; top:0; width:100%; height:6vh; min-height:28px; z-index:100; }
    #zone-b { position:fixed; top:6vh; width:100%; height:54vh; z-index:1; }
    #zone-c { position:fixed; top:60vh; width:100%; height:16vh; z-index:30; }
    #zone-d { position:fixed; bottom:0; width:100%; height:24vh; min-height:120px; z-index:20;
              background:rgba(0,0,0,0.65); border-top:1px solid rgba(255,255,255,0.15); }
  </style>
</head>
<body>
  <!-- ZONE A: Progress Bar -->
  <div id="zone-a"></div>
  
  <!-- ZONE B: Scene -->
  <div id="zone-b">
    <video id="bg-video" autoplay loop muted playsinline
      style="position:absolute;width:100%;height:100%;object-fit:cover;z-index:0">
    </video>
    <!-- scenery props, player canvas, effects, rivals -->
    <video id="player-source" style="display:none" muted playsinline></video>
    <canvas id="player-canvas" style="position:absolute;z-index:10"></canvas>
  </div>
  
  <!-- ZONE C: Mission Text -->
  <div id="zone-c" style="display:flex;align-items:center;justify-content:center;padding:0 5%">
    <p id="mission-text" style="
      color:#fff; direction:rtl; text-align:center;
      font-size:clamp(0.9rem,2.5vw,1.1rem); font-weight:600; line-height:1.5;
      text-shadow:0 1px 3px rgba(0,0,0,0.9),0 2px 8px rgba(0,0,0,0.7);
    "></p>
  </div>
  
  <!-- ZONE D: Tools -->
  <div id="zone-d" style="display:flex;align-items:center;justify-content:space-evenly;padding:0 5%">
    <!-- 3 tools injected by JS -->
  </div>

  <script>
    // ── Content (verbatim from script) ──────────────────────
    const SCENE = {
      missionText: "", // ← מוזרק מ-script_[ID].json
      tools: [
        { slot:"A", label:"", file:"", consequence:"" },
        { slot:"B", label:"", file:"", consequence:"" },
        { slot:"C", label:"", file:"", consequence:"" }
      ]
    };

    // ── Pose (from pose_map) ────────────────────────────────
    const POSE = {
      file: "",
      loopStart: 0,
      loopEnd: 0,
      holdFrame: null,
      isOneShot: false
    };

    // ── Chroma Key ──────────────────────────────────────────
    function setupChromaKey(videoEl, canvasEl) {
      const ctx = canvasEl.getContext('2d');
      videoEl.addEventListener('loadedmetadata', () => {
        canvasEl.width  = videoEl.videoWidth;
        canvasEl.height = videoEl.videoHeight;
      });
      function processFrame() {
        if (videoEl.paused || videoEl.ended) return;
        ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
        const frame = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
        const d = frame.data;
        for (let i = 0; i < d.length; i += 4) {
          if (d[i+1] > 100 && d[i+1] > d[i]*1.4 && d[i+1] > d[i+2]*1.4) d[i+3] = 0;
        }
        ctx.putImageData(frame, 0, 0);
        requestAnimationFrame(processFrame);
      }
      videoEl.addEventListener('play', processFrame);
    }

    // ── Segment Loop ────────────────────────────────────────
    function startSegmentLoop(videoEl, start, end) {
      videoEl.currentTime = start;
      videoEl.play();
      videoEl.addEventListener('timeupdate', () => {
        if (videoEl.currentTime >= end) videoEl.currentTime = start;
      });
    }

    // ── Tool Container ──────────────────────────────────────
    function buildTools() {
      const container = document.getElementById('zone-d');
      const maxSize = Math.min(window.innerWidth * 0.28, window.innerHeight * 0.20, 140);
      
      SCENE.tools.forEach(tool => {
        const wrapper = document.createElement('div');
        wrapper.style.cssText = `position:relative;width:${maxSize}px;height:${maxSize}px;cursor:pointer`;
        
        const img = document.createElement('img');
        img.src = tool.file;
        img.style.cssText = `width:100%;height:100%;object-fit:contain`;
        
        // ⓘ icon
        const icon = document.createElement('div');
        icon.textContent = 'ⓘ';
        icon.style.cssText = `
          position:absolute;top:6px;right:6px;
          width:20px;height:20px;border-radius:50%;
          background:rgba(0,0,0,0.6);color:#fff;
          font-size:0.7rem;font-weight:700;
          display:flex;align-items:center;justify-content:center;
          border:1px solid rgba(255,255,255,0.4);z-index:21;cursor:pointer;
        `;
        
        // Tooltip
        const tooltip = document.createElement('div');
        tooltip.textContent = tool.label;
        tooltip.style.cssText = `
          position:absolute;bottom:calc(100% + 8px);right:0;
          background:rgba(0,0,0,0.85);color:#fff;
          padding:5px 10px;border-radius:6px;
          font-size:0.8rem;white-space:nowrap;direction:rtl;
          opacity:0;transition:opacity 150ms;pointer-events:none;z-index:50;
        `;
        
        // Desktop hover
        icon.addEventListener('mouseenter', () => tooltip.style.opacity = '1');
        icon.addEventListener('mouseleave', () => tooltip.style.opacity = '0');
        
        // Mobile tap
        icon.addEventListener('click', (e) => {
          e.stopPropagation();
          tooltip.style.opacity = '1';
          setTimeout(() => tooltip.style.opacity = '0', 2000);
        });
        
        // Tool selection
        img.addEventListener('click', () => handleToolSelection(tool, img));
        
        wrapper.append(img, icon, tooltip);
        container.appendChild(wrapper);
      });
    }

    // ── Gear Toss + Consequence ─────────────────────────────
    async function handleToolSelection(tool, toolEl) {
      // Disable other tools
      document.querySelectorAll('#zone-d img').forEach(el => {
        if (el !== toolEl) el.style.opacity = '0.3';
      });
      
      const canvas = document.getElementById('player-canvas');
      
      // Gear toss
      await gearToss(toolEl, canvas);
      
      // Consequence — per director's brief
      switch(tool.consequence) {
        case 'deploy': await applyDeploy(toolEl, canvas); break;
        case 'wear':   await applyWear(toolEl, canvas);   break;
        case 'use':    await applyUse(toolEl);             break;
        default:       await applyHold(toolEl);
      }
      
      // Narrative beat
      showNarrativeBeat(tool.slot);
      
      // Transition
      await delay(2000);
      transitionOut();
    }

    // ── Init ────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', () => {
      document.getElementById('mission-text').textContent = SCENE.missionText;
      
      const video = document.getElementById('player-source');
      const canvas = document.getElementById('player-canvas');
      video.src = POSE.file;
      setupChromaKey(video, canvas);
      
      if (POSE.isOneShot) {
        video.play();
      } else {
        startSegmentLoop(video, POSE.loopStart, POSE.loopEnd);
      }
      
      buildTools();
    });

    // ── Helpers ─────────────────────────────────────────────
    const delay = ms => new Promise(r => setTimeout(r, ms));
    
    function gearToss(toolEl, playerCanvas) { /* מ-design_system */ }
    function applyDeploy(toolEl, canvas)    { /* מ-design_system */ }
    function applyWear(toolEl, canvas)      { /* מ-design_system */ }
    function applyUse(toolEl)               { /* מ-design_system */ }
    function applyHold(toolEl)              { return delay(1800);   }
    function showNarrativeBeat(slot)        { /* מ-script */        }
    function transitionOut()                { /* 800ms crossfade */ }
  </script>
</body>
</html>
```

---

## חוקים שאסור לשכוח

- [ ] כל טקסט — מה-script, לא מהראש
- [ ] כל path — מה-asset_manifest
- [ ] אין `video.loop = true` — תמיד segment loop
- [ ] Player video: `display:none` + canvas בלבד
- [ ] Zone D: אף פעם לא חורגת מ-24vh
- [ ] כפתורים: `#1a3a5c` או `#000` — אין זהב
- [ ] `min-height:44px` על כל כפתור

---

## חוזה חדש: STATIC fields ב‑composition.json

ה‑builder חייב לכבד את השדות האלה (יוצאים מ‑scene_composer):

### `bg.is_static_frame: true`
* **אסור** לתת ל‑bg את האטריביוטים `autoplay` או `loop`. רק `muted playsinline preload="auto"`.
* בקוד init JavaScript — לחפש את ה‑bg, לעשות `currentTime = bg.static_frame_at_seconds`, לחכות ל‑seeked event, ואז `pause()`.
* אסור לקרוא ל‑`bg.play()` בשום מקום.

### `actress.is_static_pose: true`
* טראק של standing/wait phase חייב להיות `is_pose_hold: true` עם `from_sec === to_sec === currentTime_pause_at`.
* ה‑builder לא יוצר track של `loop_until_event` עבור pose שמסומן סטטי.
* ה‑chroma key tick חייב לצייר גם כשהוידאו ב‑pause (וודא שיש `lastV/lastT` או דומה — אחרת הקנבס יישאר עם הפריים הקודם).

### בדיקה לפני delivery
* `grep -E "autoplay|loop" generated.html` — לא צריך להופיע על ה‑bg אם is_static_frame=true.
* `grep "loop_until_event" generated.html` עם match — צריך להיות רק עבור פוזות שלא מסומנות סטטיות.
* טסט ידני: לטעון את העמוד, לחכות 5 שניות, לוודא שאין שום תנועה (לא של דמות, לא של bg).
