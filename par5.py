# full_project_with_phone_ui.py
import cv2
import numpy as np
import qrcode
import os
import time
import threading
import socket
from flask import Flask, render_template_string, request, jsonify, send_file

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

# A simple threading.Event to let main thread know phone made a change (not strictly required,
# but helpful if you want to wait or redraw quickly)
phone_change_event = threading.Event()


# ---------- Helper Functions ----------
def generate_qr(slot_id):
    """Generate and save QR for slot (no duplicates).
       QR data format compatible with existing exit logic: 'Slot_<id>'"""
    qr_filename = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
    if os.path.exists(qr_filename):
        return qr_filename
    qr_data = f"Slot_{slot_id}"
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
        # Put the slot label slightly inside the polygon (first vertex)
        x, y = tuple(poly[0])
        cv2.putText(img, str(i+1), (x + 10, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return img


def show_layout(wait_ms=0):
    """Display layout in a Window (full-screen friendly)."""
    img = draw_layout_image()
    cv2.namedWindow("Parking Layout", cv2.WINDOW_NORMAL)
    # Do not force fullscreen on every platform — but try to maximize/resize to screen size
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
    # show video; user can press ESC to skip
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # resize to screen-safe size (preserve aspect)
        screen_w, screen_h = 1280, 720
        h, w = frame.shape[:2]
        scale = min(screen_w / w, screen_h / h)
        frame_resized = cv2.resize(frame, (int(w * scale), int(h * scale)))
        cv2.imshow("Car Entry", frame_resized)
        if cv2.waitKey(25) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyWindow("Car Entry")
    # short prompt after video ends
    msg = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(msg, "🚗 Car arrived. System will auto-assign a slot (or use phone).",
                (80, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 3)
    cv2.imshow("Car Entry", msg)
    cv2.waitKey(1500)
    cv2.destroyWindow("Car Entry")


# ---------- Flask phone UI (runs in background) ----------
def get_local_ip():
    """Return local IP address for the machine (used by phone QR)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def start_phone_server():
    """Start Flask phone server in background thread. Keeps serving until program exits."""
    app = Flask(__name__)

    html_template = """
    <!doctype html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Parking Layout (Phone)</title>
        <style>
          body { font-family: Arial, sans-serif; text-align:center; background:#f7f7f7; padding:10px; }
          .grid { display:flex; flex-wrap:wrap; justify-content:center; gap:10px; }
          .slot {
            width:90px; height:90px; border-radius:8px; line-height:90px;
            font-size:20px; color:white; cursor:pointer; user-select:none;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
          }
          .Free { background:#28a745; }
          .Occupied { background:#dc3545; opacity:0.95; cursor:not-allowed; }
          .info { margin:12px; font-size:16px; }
          .qr { margin-top:12px; }
          button { margin-top:12px; padding:8px 12px; font-size:16px; }
        </style>
      </head>
      <body>
        <h2>🅿 Tap a slot to reserve</h2>
        <div class="info">Green = Free • Red = Occupied</div>
        <div class="grid" id="grid"></div>
        <div id="result"></div>

    <script>
    async function refreshSlots() {
      let r = await fetch('/status');
      let data = await r.json();
      const grid = document.getElementById('grid');
      grid.innerHTML = '';
      for (let i=0;i<data.slots.length;i++) {
        const s = document.createElement('div');
        s.className = 'slot ' + data.slots[i];
        s.innerText = 'S' + (i+1);
        if (data.slots[i] === 'Free') {
          s.onclick = async () => {
            const res = await fetch('/select?idx=' + i);
            const j = await res.json();
            if (j.status === 'ok') {
              // show exit QR and download link
              document.getElementById('result').innerHTML = `
                <h3>✅ You reserved S${i+1}</h3>
                <div class="qr">
                  <img src="/exit_qr/${i+1}" width="200"><br>
                  <a href="/exit_qr/${i+1}" download="exit_S${i+1}.png">
                    <button>Download Exit QR</button>
                  </a>
                </div>
                <div style="margin-top:10px"><button onclick="location.reload()">Close</button></div>
              `;
            } else {
              alert(j.message);
              location.reload();
            }
          };
        }
        grid.appendChild(s);
      }
    }

    // initial load
    refreshSlots();
    // do not auto-refresh constantly; allow manual refresh button if needed
    </script>
      </body>
    </html>
    """

    @app.route("/status")
    def status():
        # return current slot_status array (so phone can render)
        return jsonify({"slots": spot_status})

    @app.route("/")
    def index():
        return render_template_string(html_template)

    @app.route("/select")
    def select():
        """Phone selects a free slot by index (0-based)."""
        idx = request.args.get("idx")
        if idx is None:
            return jsonify({"status": "error", "message": "Invalid request"})
        try:
            i = int(idx)
        except:
            return jsonify({"status": "error", "message": "Bad index"})
        if i < 0 or i >= len(spot_status):
            return jsonify({"status": "error", "message": "Index out of range"})
        # Acquire selection: only allow if free
        if spot_status[i] != "Free":
            return jsonify({"status": "error", "message": "Slot already occupied"})
        spot_status[i] = "Occupied"
        # generate exit QR (Slot_<n>) and save same as desktop expects
        generate_qr(i + 1)
        phone_change_event.set()
        print(f"📱 Phone reserved Slot {i+1}")
        return jsonify({"status": "ok", "message": f"Slot {i+1} reserved"})

    @app.route("/exit_qr/<slot_id>")
    def exit_qr(slot_id):
        """Serve the exit QR image for slot (slot_id is 1-based string)."""
        fname = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
        if not os.path.exists(fname):
            return "QR not found", 404
        return send_file(fname, mimetype="image/png")

    @app.route("/free")
    def free_slot():
        """Optional: free slot via web link (e.g., QR can point here)."""
        slot = request.args.get("slot")  # expects "S<number>" or plain number
        if not slot:
            return "Missing slot", 400
        # try to parse either "S3" or "3"
        try:
            if slot.startswith("S") or slot.startswith("s"):
                n = int(slot[1:])
            else:
                n = int(slot)
        except:
            return "Bad slot id", 400
        if 1 <= n <= len(spot_status):
            spot_status[n - 1] = "Free"
            # delete QR file if exists
            f = os.path.join(QR_FOLDER, f"slot_{n}.png")
            try:
                if os.path.exists(f):
                    os.remove(f)
            except:
                pass
            phone_change_event.set()
            return f"Slot {n} freed"
        return "Out of range", 400

    # Run Flask server (non-blocking) on background thread
    def run_app():
        ip = get_local_ip()
        url = f"http://{ip}:5000"
        print(f"\n🌐 Phone UI available at: {url}")
        # generate & open layout QR for convenience
        try:
            qrcode.make(url).save("layout_qr.png")
            if os.name == "nt":
                os.system("start layout_qr.png")
            else:
                # mac / linux open (best effort)
                try:
                    os.system("xdg-open layout_qr.png")
                except:
                    try:
                        os.system("open layout_qr.png")
                    except:
                        pass
        except Exception:
            pass
        # start server (use host 0.0.0.0 so phone can reach it)
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)

    t = threading.Thread(target=run_app, daemon=True)
    t.start()
    return t


# ---------- Robust handle_exit implementation (unchanged behavior) ----------
def handle_exit():
    """
    Shows a stable, sorted list of QR PNG files from QR_FOLDER.
    Accepts:
     - list index (1..N)
     - exact filename (slot_3.png)
     - absolute path to a file
    Then displays the QR, decodes it with OpenCV QRCodeDetector, marks slot Free, deletes QR.
    """
    qr_files = sorted([f for f in os.listdir(QR_FOLDER) if f.lower().endswith(".png")], key=lambda x: x.lower())
    if not qr_files:
        print("🟨 No QR codes found (no cars to exit).")
        return

    print("\n📂 QR files in folder:")
    for idx, name in enumerate(qr_files, 1):
        slot_tag = ""
        if name.lower().startswith("slot_"):
            try:
                slot_no = int(name.split("_")[1].split(".")[0])
                slot_tag = f" (slot {slot_no})"
            except:
                slot_tag = ""
        print(f" {idx}. {name}{slot_tag}")

    raw = input("\nEnter list number or filename to scan (e.g. 1 or slot_3.png): ").strip()
    if raw == "":
        print("❌ No input provided. Cancelled.")
        return

    chosen_path = None

    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(qr_files):
            chosen_path = os.path.join(QR_FOLDER, qr_files[n - 1])
        else:
            alt_name = f"slot_{n}.png"
            if alt_name in qr_files:
                chosen_path = os.path.join(QR_FOLDER, alt_name)

    if not chosen_path:
        candidate = raw
        cand_in_folder = os.path.join(QR_FOLDER, candidate)
        if os.path.isfile(cand_in_folder):
            chosen_path = cand_in_folder
        elif os.path.isabs(candidate) and os.path.isfile(candidate):
            chosen_path = candidate

    if not chosen_path:
        import re
        m = re.search(r"(\d+)", raw)
        if m:
            n = int(m.group(1))
            alt_name = f"slot_{n}.png"
            if alt_name in qr_files:
                chosen_path = os.path.join(QR_FOLDER, alt_name)

    if not chosen_path or not os.path.isfile(chosen_path):
        print("❌ Could not resolve your input to a valid QR file. Please try again.")
        return

    qr_img = cv2.imread(chosen_path)
    if qr_img is None:
        print("❌ Failed to open the chosen QR image.")
        return

    cv2.namedWindow("QR Scanner", cv2.WINDOW_NORMAL)
    try:
        cv2.setWindowProperty("QR Scanner", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except:
        pass
    cv2.imshow("QR Scanner", qr_img)
    cv2.waitKey(1200)

    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(qr_img)
    cv2.destroyWindow("QR Scanner")

    if not data:
        print("❌ QR could not be decoded.")
        return

    print(f"🔍 Decoded QR data: {data}")

    if not data.startswith("Slot_"):
        print("❌ Unexpected QR format.")
        return

    try:
        slot_num = int(data.split("_")[1])
        if not (1 <= slot_num <= len(spots)):
            print("❌ Slot number in QR is out of range.")
            return
    except Exception:
        print("❌ Could not parse slot number from QR.")
        return

    # mark free and delete file
    spot_status[slot_num - 1] = "Free"

    try:
        os.remove(chosen_path)
        print(f"🗑 Deleted QR file: {chosen_path}")
    except Exception as e:
        print(f"⚠ Could not delete QR file: {e}")

    print(f"✅ Car exited from Slot {slot_num}. Slot is now FREE.")
    show_layout(wait_ms=1500)


# ---------- Entry / Exit handlers ----------
def handle_entry():
    """
    Laptop entry: video plays, then ALLOCATE FIRST AVAILABLE slot automatically.
    The phone UI can still be used for manual booking, which updates spot_status in memory.
    """
    play_entry_video()

    # find first free slot
    try:
        slot_idx = next(i for i, s in enumerate(spot_status) if s == "Free")
    except StopIteration:
        print("⚠ No free slots available.")
        return

    # allocate it (phone selection would also set this)
    spot_status[slot_idx] = "Occupied"
    generate_qr(slot_idx + 1)
    print(f"🅿 Auto-assigned Slot {slot_idx + 1} to arriving car.")
    # show updated layout for a moment
    show_layout(wait_ms=1000)


# ---------- Main loop ----------
def main():
    # start the web UI thread (phone)
    print("🔁 Starting phone UI server (Flask) in background...")
    start_phone_server()
    time.sleep(0.8)  # small pause so QR file is created and server prints the URL

    while True:
        print("\n=== Indoor Smart Parking System ===")
        print("1. Car Entry (video + auto-assign)")
        print("2. Car Exit (scan QR image)")
        print("3. View Layout (laptop)")
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