# par_final.py
import cv2
import numpy as np
import qrcode
import os
import time
import threading
import socket
import random

# Flask imports are used only when phone-selection runs
try:
    from flask import Flask, render_template_string, request, jsonify, send_file
    from werkzeug.serving import make_server
except Exception:
    Flask = None
    make_server = None

# ---------- SETTINGS ----------
LAYOUT_FILE = "layout.png"
SPOTS_FILE = "parking_spots.npy"
VIDEO_FILE = "car_entry.mp4"
QR_FOLDER = "qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)
# ------------------------------

# ---------- Load layout and parking spots ----------
if not os.path.exists(LAYOUT_FILE):
    print("❌ Layout image not found.")
    exit()

if not os.path.exists(SPOTS_FILE):
    print("❌ Parking spot data not found. Run mark_spots.py first.")
    exit()

layout_img = cv2.imread(LAYOUT_FILE)
spots = np.load(SPOTS_FILE, allow_pickle=True)
print(f"✅ Loaded layout and {len(spots)} parking spots.")

# Initialize slot status (all free initially)
spot_status = ["Free"] * len(spots)
exit_codes = {}  # slot -> 4-digit code


# ---------- Helper Functions ----------
def generate_qr(slot_id):
    """Generate and save QR for slot (no duplicates)."""
    qr_filename = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
    if os.path.exists(qr_filename):
        return qr_filename
    qr_data = f"Slot_{slot_id}_QR"
    qr_img = qrcode.make(qr_data)
    qr_img.save(qr_filename)
    print(f"🟩 QR saved: {qr_filename}")
    return qr_filename


def draw_layout_image():
    """Return current layout image with slot colors."""
    img = layout_img.copy()
    for i, poly in enumerate(spots):
        color = (0, 255, 0) if spot_status[i] == "Free" else (0, 0, 255)
        cv2.polylines(img, [np.array(poly, np.int32)], True, color, 2)
        pos = tuple(poly[0]) if len(poly) > 0 else (10, 20)
        cv2.putText(img, str(i+1), pos, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return img


def show_layout(wait_ms=0):
    img = draw_layout_image()
    cv2.namedWindow("Parking Layout", cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty("Parking Layout", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except Exception:
        pass
    cv2.imshow("Parking Layout", img)
    cv2.waitKey(wait_ms)
    cv2.destroyWindow("Parking Layout")


def play_entry_video():
    cap = cv2.VideoCapture(VIDEO_FILE)
    if not cap.isOpened():
        print("⚠ Entry video not found or can't open. Skipping.")
        return
    cv2.namedWindow("Car Entry", cv2.WINDOW_NORMAL)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Car Entry", frame)
        if cv2.waitKey(25) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyWindow("Car Entry")
    msg = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(msg, "🚗 Please scan the QR to select a slot on your phone",
                (40, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
    cv2.imshow("Car Entry", msg)
    cv2.waitKey(1500)
    cv2.destroyWindow("Car Entry")


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


# ---------- Phone-based Selection with layout image ----------
def select_parking_slot(timeout=60):
    import base64

    if Flask is None or make_server is None:
        print("❌ Flask not installed. Run: pip install flask werkzeug")
        return None

    app = Flask(__name__)
    selection_event = threading.Event()
    selected_idx = {"val": None}
    lock = threading.Lock()

    # convert layout.png to base64 for display
    _, buffer = cv2.imencode(".png", layout_img)
    layout_b64 = base64.b64encode(buffer).decode("utf-8")
    spots_js = [[list(map(int, pt)) for pt in poly] for poly in spots]

    html = f"""
    <!doctype html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Parking Layout</title>
      <style>
        body {{ margin:0; background:#111; overflow:hidden; touch-action:none; }}
        canvas {{ background:#000; display:block; margin:auto; touch-action:none; }}
      </style>
    </head>
    <body>
      <canvas id="layoutCanvas" width="1280" height="720"></canvas>
      <script>
        const imgData = "data:image/png;base64,{layout_b64}";
        const spots = {spots_js};
        const status = {spot_status};
        const canvas = document.getElementById('layoutCanvas');
        const ctx = canvas.getContext('2d');
        let scale = 1, originX = 0, originY = 0, dragging = false, lastX=0, lastY=0;
        const img = new Image();
        img.onload = drawAll;
        img.src = imgData;

        function drawAll() {{
          ctx.save();
          ctx.setTransform(scale,0,0,scale,originX,originY);
          ctx.clearRect(-originX/scale, -originY/scale, canvas.width/scale, canvas.height/scale);
          ctx.drawImage(img, 0, 0);
          for (let i=0;i<spots.length;i++) {{
            const poly = spots[i];
            ctx.beginPath();
            ctx.moveTo(poly[0][0], poly[0][1]);
            for (let j=1;j<poly.length;j++) ctx.lineTo(poly[j][0], poly[j][1]);
            ctx.closePath();
            ctx.lineWidth=3;
            ctx.strokeStyle = status[i]==='Free' ? '#00FF00' : '#FF0000';
            ctx.stroke();
            ctx.font="20px Arial";
            ctx.fillStyle = status[i]==='Free' ? '#00FF00' : '#FF0000';
            ctx.fillText('S'+(i+1), poly[0][0]+5, poly[0][1]+20);
          }}
          ctx.restore();
        }}

        canvas.addEventListener('wheel', e => {{
          e.preventDefault();
          const zoom = e.deltaY < 0 ? 1.1 : 0.9;
          scale *= zoom;
          drawAll();
        }});

        canvas.addEventListener('mousedown', e => {{
          dragging=true; lastX=e.offsetX; lastY=e.offsetY;
        }});
        canvas.addEventListener('mouseup', ()=>dragging=false);
        canvas.addEventListener('mousemove', e => {{
          if (dragging) {{
            originX += e.offsetX - lastX;
            originY += e.offsetY - lastY;
            lastX = e.offsetX; lastY = e.offsetY;
            drawAll();
          }}
        }});

        canvas.addEventListener('click', e => {{
          const x = (e.offsetX - originX)/scale;
          const y = (e.offsetY - originY)/scale;
          for (let i=0;i<spots.length;i++) {{
            const poly = spots[i];
            if (pointInPolygon(x,y,poly) && status[i]==='Free') {{
              fetch('/select?idx='+i)
                .then(r=>r.json())
                .then(j=>{
                  if(j.status==='ok'){{
                    document.body.innerHTML = '<center><h2>✅ Slot S'+(i+1)+' Reserved</h2>' +
                      '<img src="'+j.exit_qr+'" width="220"><br>'+
                      '<p>Exit Code: <b>'+j.exit_code+'</b></p>'+
                      '<a href="'+j.exit_qr+'" download>Download Exit QR</a></center>';
                  }} else alert(j.message);
                }});
              return;
            }}
          }}
        }});

        function pointInPolygon(x,y,poly){{
          let inside=false;
          for(let i=0,j=poly.length-1;i<poly.length;j=i++){{
            const xi=poly[i][0], yi=poly[i][1];
            const xj=poly[j][0], yj=poly[j][1];
            const intersect=((yi>y)!=(yj>y))&&(x<(xj-xi)*(y-yi)/(yj-yi)+xi);
            if(intersect) inside=!inside;
          }}
          return inside;
        }}
      </script>
    </body>
    </html>
    """

    @app.route("/")
    def layout_page():
        return html

    @app.route("/select")
    def phone_select():
        idx = request.args.get("idx", type=int)
        if idx is None or idx < 0 or idx >= len(spot_status):
            return jsonify({"status": "error", "message": "Invalid slot"}), 400
        with lock:
            if spot_status[idx] != "Free":
                return jsonify({"status": "error", "message": "Already occupied"}), 400
            spot_status[idx] = "Occupied"
            ip = get_local_ip()
            exit_url = f"http://{ip}:5000/exit_direct?slot={idx+1}"
            os.makedirs("qrs", exist_ok=True)
            qrcode.make(exit_url).save(f"qrs/exit_S{idx+1}.png")
            exit_code = random.randint(1000, 9999)
            exit_codes[idx] = exit_code
            selected_idx["val"] = idx
            selection_event.set()
            print(f"🚗 Slot S{idx+1} booked. Exit code: {exit_code}")
            return jsonify({"status": "ok", "exit_qr": f"/exit_qr/S{idx+1}", "exit_code": exit_code})

    @app.route("/exit_qr/<name>")
    def serve_exit_qr(name):
        path = os.path.join("qrs", f"exit_{name}.png")
        if os.path.isfile(path):
            return send_file(path, mimetype="image/png")
        return ("", 404)

    @app.route("/exit_direct")
    def exit_direct():
        slot = request.args.get("slot", type=int)
        if slot is None or slot < 1 or slot > len(spots):
            return "Invalid slot", 400
        idx = slot - 1
        spot_status[idx] = "Free"
        code = exit_codes.pop(idx, None)
        path = os.path.join("qrs", f"exit_S{slot}.png")
        if os.path.exists(path):
            os.remove(path)
        return f"<h2>🚗 Slot S{slot} freed. Exit successful.</h2>"

    server = make_server("0.0.0.0", 5000, app)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    ip = get_local_ip()
    layout_url = f"http://{ip}:5000"
    qrcode.make(layout_url).save("layout_qr.png")
    os.system("start layout_qr.png" if os.name == "nt" else "xdg-open layout_qr.png")
    print(f"📱 Scan layout_qr.png or open {layout_url} on phone to select slot.")

    if not selection_event.wait(timeout):
        print("⚠ No selection made (timeout).")
        server.shutdown()
        return None

    server.shutdown()
    return selected_idx["val"]


# ---------- Entry & Exit ----------
def handle_entry():
    play_entry_video()
    slot_idx = select_parking_slot(timeout=60)
    if slot_idx is None:
        print("❌ No slot selected.")
        return
    spot_status[slot_idx] = "Occupied"
    qr_path = generate_qr(slot_idx + 1)
    print(f"🅿 Slot S{slot_idx + 1} booked. Exit code: {exit_codes[slot_idx]}")
    print(f"Exit QR saved: {qr_path}")
    show_layout(wait_ms=1500)


def handle_exit():
    code_input = input("Enter your 4-digit exit code: ").strip()
    if not code_input.isdigit():
        print("❌ Invalid input.")
        return
    code_input = int(code_input)
    found = None
    for idx, code in exit_codes.items():
        if code == code_input:
            found = idx
            break
    if found is None:
        print("❌ No matching exit code.")
        return
    spot_status[found] = "Free"
    exit_codes.pop(found, None)
    path = os.path.join("qrs", f"exit_S{found+1}.png")
    if os.path.exists(path):
        os.remove(path)
    print(f"✅ Car exited from Slot S{found+1}. Slot now FREE.")
    show_layout(wait_ms=1500)


# ---------- Main ----------
def main():
    while True:
        print("\n=== Indoor Smart Parking System ===")
        print("1. Car Entry")
        print("2. Car Exit (use code)")
        print("3. View Layout")
        print("4. Quit")
        ch = input("Choice: ").strip()
        if ch == "1":
            handle_entry()
        elif ch == "2":
            handle_exit()
        elif ch == "3":
            show_layout()
        elif ch == "4":
            print("👋 Bye!")
            break
        else:
            print("❌ Invalid choice.")


if __name__ == "__main__":
    main()