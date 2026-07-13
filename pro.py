import cv2, base64, threading, socket
from flask import Flask, render_template_string
from werkzeug.serving import make_server

app = Flask(__name__)

LAYOUT_FILE = "layout.png"

# --- Load & resize safely ---
img = cv2.imread(LAYOUT_FILE)
if img is None:
    print("❌ layout.png not found. Put your layout image in same folder.")
    exit()

h, w = img.shape[:2]
max_w, max_h = 800, 600  # safe size for phones
scale = min(max_w / w, max_h / h)
new_size = (int(w * scale), int(h * scale))
img_small = cv2.resize(img, new_size)

# Compress before encoding
encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
_, buffer = cv2.imencode(".jpg", img_small, encode_param)
layout_b64 = base64.b64encode(buffer).decode("utf-8")

# --- HTML ---
html = f"""
<!doctype html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1.0, user-scalable=yes'>
  <title>Parking Layout</title>
  <style>
    body {{ margin:0; background:#000; overflow:hidden; }}
    #container {{ width:100vw; height:100vh; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
    img {{ max-width:100%; height:auto; transform-origin:center center; transition:transform 0.05s ease-out; }}
  </style>
</head>
<body>
  <div id="container">
    <img id="layout" src="data:image/jpeg;base64,{layout_b64}" alt="Layout">
  </div>
  <script>
    const img = document.getElementById('layout');
    let scale = 1.0, startDist = 0;

    document.addEventListener('touchstart', e => {{
      if (e.touches.length === 2) {{
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        startDist = Math.hypot(dx, dy);
      }}
    }});

    document.addEventListener('touchmove', e => {{
      if (e.touches.length === 2) {{
        e.preventDefault();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const newDist = Math.hypot(dx, dy);
        const factor = newDist / startDist;
        img.style.transform = scale(${{scale * factor}});
      }}
    }});

    document.addEventListener('touchend', e => {{
      if (e.touches.length === 0) {{
        const match = /scale\\(([^)]+)\\)/.exec(img.style.transform);
        if (match) scale = parseFloat(match[1]);
      }}
    }});
  </script>
</body>
</html>
"""

@app.route("/")
def layout_page():
    return render_template_string(html)

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def start_server():
    server = make_server("0.0.0.0", 5000, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server

# --- Run ---
ip = get_local_ip()
start_server()
print(f"📱 Open this on your phone browser: http://{ip}:5000")
print("✅ Layout loaded. You can zoom in/out safely.")