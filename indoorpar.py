# par_final.py
import cv2
import numpy as np
import qrcode
import os
import time
import threading
import socket
import random  # ✅ Added for generating random exit codes

# Flask imports are used only when phone-selection runs
try:
    from flask import Flask, render_template_string, request, jsonify
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

spot_status = ["Free"] * len(spots)
exit_codes = {}  # ✅ slot_number:int -> exit_code:str


# ---------- Helper Functions ----------
def generate_qr(slot_id):
    qr_filename = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
    if os.path.exists(qr_filename):
        return qr_filename
    qr_data = f"Slot_{slot_id}_QR"
    qr_img = qrcode.make(qr_data)
    qr_img.save(qr_filename)
    print(f"🟩 QR saved: {qr_filename}")
    return qr_filename


def draw_layout_image():
    img = layout_img.copy()
    for i, poly in enumerate(spots):
        color = (0, 255, 0) if spot_status[i] == "Free" else (0, 0, 255)
        cv2.polylines(img, [np.array(poly, np.int32)], True, color, 2)
        pos = tuple(poly[0]) if len(poly) > 0 else (20, 20)
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
    if wait_ms == 0:
        cv2.waitKey(0)
    else:
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


# ---------- Phone-based selection ----------
def select_parking_slot(timeout=60):
    if Flask is None or make_server is None:
        print("❌ Flask or werkzeug not installed.")
        return None

    app = Flask(__name__)
    selection_event = threading.Event()
    selected_idx = {"val": None}
    lock = threading.Lock()

    html_template = """
    <!doctype html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Parking Layout</title>
        <style>
          body { font-family: Arial, sans-serif; text-align:center; background:#f7f7f7; padding:20px; }
          #grid { display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }
          .slot { width:90px; height:90px; line-height:90px; border-radius:8px; color:white; font-size:20px;
                  display:inline-block; cursor:pointer; user-select:none; box-shadow:0 2px 6px rgba(0,0,0,0.15); }
          .Free { background:#28a745; }
          .Occupied { background:#dc3545; cursor:not-allowed; opacity:0.9; }
          .info { margin:12px; font-size:16px; }
          #qr { margin-top:16px; }
        </style>
      </head>
      <body>
        <h2>🅿 Tap a free slot to reserve</h2>
        <div class="info">Green = Free • Red = Occupied</div>
        <div id="grid"></div>
        <div id="qr"></div>
        <script>
          const slots = {{ slots|tojson }};
          function render() {
            const grid = document.getElementById('grid'); grid.innerHTML = '';
            for (let i=0; i<slots.length; i++) {
              const d = document.createElement('div');
              d.className = 'slot ' + (slots[i] === 'Free' ? 'Free' : 'Occupied');
              d.innerText = 'S' + (i+1);
              if (slots[i] === 'Free') d.onclick = () => selectSlot(i);
              grid.appendChild(d);
            }
          }
          function selectSlot(i) {
            fetch('/select?idx=' + i)
              .then(r => r.json())
              .then(j => {
                if (j.status === 'ok') {
                  document.getElementById('grid').style.display='none';
                  const qrDiv = document.getElementById('qr');
                  qrDiv.innerHTML = '<h3>✅ Slot S' + (i+1) + ' reserved</h3>';
                  qrDiv.innerHTML += '<img src="' + j.exit_qr + '" width="220"><br>';
                  qrDiv.innerHTML += '<p style="font-size:18px;">Exit Code: <b>' + j.exit_code + '</b></p>';  /* ✅ show code */
                } else { alert(j.message || 'Error'); }
              });
          }
          render();
        </script>
      </body>
    </html>
    """

    @app.route("/")
    def phone_layout():
        return render_template_string(html_template, slots=spot_status)

    @app.route("/select")
    def phone_select():
        idx = request.args.get("idx")
        if idx is None:
            return jsonify({"status": "error", "message": "Invalid request"}), 400
        try:
            i = int(idx)
        except:
            return jsonify({"status": "error", "message": "Invalid index"}), 400
        with lock:
            if i < 0 or i >= len(spot_status):
                return jsonify({"status": "error", "message": "Index out of range"}), 400
            if spot_status[i] != "Free":
                return jsonify({"status": "error", "message": "Slot occupied"}), 400

            spot_status[i] = "Occupied"
            ip = get_local_ip()
            exit_url = f"http://{ip}:5000/exit_direct?slot={i+1}"
            os.makedirs("qrs", exist_ok=True)
            exit_qr_path = f"qrs/exit_S{i+1}.png"
            qrcode.make(exit_url).save(exit_qr_path)

            # ✅ generate random 4-digit exit code
            code = str(random.randint(1000, 9999))
            exit_codes[i+1] = code
            print(f"🔑 Exit Code for Slot {i+1} = {code}")

            selected_idx["val"] = i
            selection_event.set()
            return jsonify({"status": "ok", "exit_qr": f"/exit_qr/S{i+1}", "exit_code": code})

    @app.route("/exit_qr/<name>")
    def serve_exit_qr(name):
        from flask import send_file
        path = os.path.join("qrs", f"exit_{name}.png")
        if os.path.isfile(path):
            return send_file(path, mimetype="image/png")
        return ("", 404)

    @app.route("/exit_direct")
    def exit_direct():
        slot = request.args.get("slot")
        try:
            slot_no = int(slot)
        except:
            return "Invalid", 400
        idx = slot_no - 1
        if 0 <= idx < len(spot_status):
            spot_status[idx] = "Free"
            path = os.path.join("qrs", f"exit_S{slot_no}.png")
            if os.path.exists(path):
                os.remove(path)
            exit_codes.pop(slot_no, None)  # ✅ remove code
            return f"<h2>🚗 Slot S{slot_no} freed. You may close.</h2>"
        return "Invalid slot", 400

    server = make_server("0.0.0.0", 5000, app)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    ip = get_local_ip()
    layout_url = f"http://{ip}:5000"
    qrcode.make(layout_url).save("layout_qr.png")
    os.system("start layout_qr.png" if os.name == "nt" else "xdg-open layout_qr.png || open layout_qr.png")
    print(f"🌐 Scan layout_qr.png or open {layout_url} on your phone to select slot.")
    print(f"⏳ Waiting {timeout}s for phone selection...")
    waited = selection_event.wait(timeout)
    time.sleep(0.2)
    try: server.shutdown()
    except: pass

    if not waited:
        print("⚠ No selection made.")
        return None
    sel = selected_idx["val"]
    print(f"✅ Phone selected slot: S{sel+1}")
    return sel


# ---------- Exit Handler ----------
def handle_exit():
    """Exit now asks for exit code (simulating scanning QR at gate)."""
    code_in = input("Enter exit code (shown on phone): ").strip()
    found = None
    for slot_no, code in exit_codes.items():
        if code == code_in:
            found = slot_no
            break
    if not found:
        print("❌ Invalid exit code.")
        return

    spot_status[found - 1] = "Free"
    exit_codes.pop(found, None)
    path = os.path.join("qrs", f"exit_S{found}.png")
    if os.path.exists(path):
        os.remove(path)
    path2 = os.path.join(QR_FOLDER, f"slot_{found}.png")
    if os.path.exists(path2):
        os.remove(path2)

    print(f"✅ Car exited from Slot {found}. Slot is now FREE.")
    show_layout(wait_ms=1500)


# ---------- Entry ----------
def handle_entry():
    play_entry_video()
    slot_idx = select_parking_slot(timeout=60)
    if slot_idx is None:
        print("❌ No slot selected.")
        return

    spot_status[slot_idx] = "Occupied"
    qr_path = generate_qr(slot_idx + 1)

    # ✅ Get the exit code that was assigned earlier in select_parking_slot()
    exit_code = exit_codes.get(slot_idx + 1, "----")

    print(f"\n🅿 Slot S{slot_idx + 1} booked successfully!")
    print(f"📄 Exit QR saved at: {qr_path}")
    print(f"🔑 Exit Code for Slot S{slot_idx + 1}: {exit_code}")
    print("📱 (Shown on phone under QR as well — use this to exit)\n")

    show_layout(wait_ms=1500)

# ---------- Main Loop ----------
def main():
    while True:
        print("\n=== Indoor Smart Parking System ===")
        print("1. Car Entry")
        print("2. Car Exit (use exit code)")
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
            print("Bye!")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    main()