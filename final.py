# par_final.py
import cv2
import numpy as np
import qrcode
import os
import time
import threading
import socket

# Flask imports are used only when phone-selection runs
try:
    from flask import Flask, render_template_string, request, jsonify
    from werkzeug.serving import make_server
except Exception:
    # We'll notify user inside select_parking_slot if Flask missing
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


# ---------- Helper Functions ----------
def generate_qr(slot_id):
    """Generate and save QR for slot (no duplicates)."""
    qr_filename = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
    if os.path.exists(qr_filename):
        # Already exists — return the path
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
        # Put text near first poly point (ensure valid tuple)
        try:
            pos = tuple(poly[0])
        except:
            pos = (10 + i*20, 30 + i*10)
        cv2.putText(img, str(i+1), pos, cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return img


def show_layout(wait_ms=0):
    img = draw_layout_image()
    cv2.namedWindow("Parking Layout", cv2.WINDOW_NORMAL)
    # Try to set fullscreen for presentation (works on most platforms)
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
    # Not forcing fullscreen to avoid cropping on some systems
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Car Entry", frame)
        if cv2.waitKey(25) & 0xFF == 27:
            break
    cap.release()
    cv2.destroyWindow("Car Entry")
    # short message
    msg = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(msg, "🚗 Please scan the QR to select a slot on your phone",
                (40, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
    cv2.imshow("Car Entry", msg)
    cv2.waitKey(1500)
    cv2.destroyWindow("Car Entry")


def get_local_ip():
    """Return local IP address for the machine (used by phone QR)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't actually need to connect; used to pick the correct outgoing interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


# ---------- Phone-based selection (replaces laptop selection) ----------
def select_parking_slot(timeout=60):
    """
    Start a tiny Flask server (in background thread) and present a phone UI.
    Returns the selected slot index (0-based) if a phone user selects one within timeout,
    otherwise returns None.

    Requirements: flask & werkzeug must be installed in the same venv.
    """
    if Flask is None or make_server is None:
        print("❌ Flask or werkzeug not installed. Install with: pip install flask werkzeug")
        return None

    app = Flask(__name__)
    selection_event = threading.Event()
    selected_idx = {"val": None}
    lock = threading.Lock()

    # HTML template for phone (boxes S1, S2, ...)
    html_template = """
    <!doctype html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
        <title>Parking Layout</title>
        <style>
          body { font-family: Arial, sans-serif; text-align:center; background:#f7f7f7; padding:20px; }
          #grid { display:flex; flex-wrap:wrap; justify-content:center; gap:12px; }
          .slot {
            width:90px; height:90px; line-height:90px; border-radius:8px; color:white; font-size:20px;
            display:inline-block; cursor:pointer; user-select:none;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
          }
          .Free { background:#28a745; }
          .Occupied { background:#dc3545; cursor:not-allowed; opacity:0.9; }
          .info { margin:12px; font-size:16px; }
          #qr { margin-top:16px; }
          #download { margin-top:8px; display:block; }
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
              if (slots[i] === 'Free') {
                d.onclick = () => selectSlot(i);
              }
              grid.appendChild(d);
            }
          }
          function selectSlot(i) {
            fetch('/select?idx=' + i)
              .then(r => r.json())
              .then(j => {
                if (j.status === 'ok') {
                  // show exit QR returned by server
                  document.getElementById('grid').style.display='none';
                  const qrDiv = document.getElementById('qr');
                  qrDiv.innerHTML = '<h3>✅ Slot S' + (i+1) + ' reserved</h3>';
                  qrDiv.innerHTML += '<img src="' + j.exit_qr + '" width="220"><br>';
                  qrDiv.innerHTML += '<a id="download" href="' + j.exit_qr + '" download>Download Exit QR</a>';
                } else {
                  alert(j.message || 'Error');
                }
              });
          }
          render();
        </script>
      </body>
    </html>
    """

    @app.route("/")
    def phone_layout():
        # Provide current slot_status to page
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
                return jsonify({"status": "error", "message": "Slot already occupied"}), 400
            # mark occupied immediately
            spot_status[i] = "Occupied"
            # generate exit QR url (server will expose /exit?slot=Sx)
            ip = get_local_ip()
            exit_url = f"http://{ip}:5000/exit_direct?slot={i+1}"
            os.makedirs("qrs", exist_ok=True)
            exit_qr_path = f"qrs/exit_S{i+1}.png"
            qrcode.make(exit_url).save(exit_qr_path)
            # record and notify main thread
            selected_idx["val"] = i
            selection_event.set()
            # return path for phone to show the qr image (we serve it below)
            return jsonify({"status": "ok", "exit_qr": f"/exit_qr/S{i+1}"})

    @app.route("/exit_qr/<name>")
    def serve_exit_qr(name):
        from flask import send_file
        path = os.path.join("qrs", f"exit_{name}.png")
        if os.path.isfile(path):
            return send_file(path, mimetype="image/png")
        return ("", 404)

    @app.route("/exit_direct")
    def exit_direct():
        """This endpoint simulates scanning exit QR (if someone visits exit_url)."""
        slot = request.args.get("slot")
        try:
            slot_no = int(slot)
        except:
            return "Invalid", 400
        idx = slot_no - 1
        if 0 <= idx < len(spot_status):
            spot_status[idx] = "Free"
            # remove generated QR file if exists
            path = os.path.join("qrs", f"exit_S{slot_no}.png")
            try:
                if os.path.exists(path):
                    os.remove(path)
            except:
                pass
            return f"<h2>🚗 Slot S{slot_no} freed. You may close.</h2>"
        return "Invalid slot", 400

    # start server using Werkzeug make_server so we can shutdown programmatically
    server = make_server("0.0.0.0", 5000, app)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    # generate layout QR (url to root)
    ip = get_local_ip()
    layout_url = f"http://{ip}:5000"
    try:
        qrcode.make(layout_url).save("layout_qr.png")
        # open layout QR on laptop (so you can scan)
        if os.name == "nt":
            os.system("start layout_qr.png")
        elif os.name == "posix":
            # try xdg-open or open
            if os.system("xdg-open layout_qr.png") != 0:
                os.system("open layout_qr.png")
    except Exception:
        pass

    print(f"🌐 Scan the layout QR (layout_qr.png) or open {layout_url} on your phone to select a slot.")
    print(f"⏳ Waiting up to {timeout}s for phone selection...")

    waited = selection_event.wait(timeout=timeout)
    # give a tiny moment for last response to settle
    time.sleep(0.2)

    # shutdown server cleanly
    try:
        server.shutdown()
    except Exception:
        pass

    if not waited:
        print("⚠ No selection made from phone (timeout).")
        return None

    sel = selected_idx["val"]
    print(f"✅ Phone selected slot: S{sel+1}")
    return sel


# ---------- Robust handle_exit implementation ----------
def handle_exit():
    """
    Shows a stable, sorted list of QR PNG files from QR_FOLDER.
    Accepts:
     - list index (1..N)
     - exact filename (slot_3.png)
    Then displays the QR, decodes it with OpenCV QRCodeDetector, marks slot Free, deletes QR.
    (Minor improvements to keep consistent)
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
            chosen_path = os.path.join(QR_FOLDER, qr_files[n-1])
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
    # Play the entry video (if exists) and then start phone selection
    play_entry_video()

    # Phone-based selection flow: will generate layout QR and wait for phone user
    slot_idx = select_parking_slot(timeout=60)
    if slot_idx is None:
        print("❌ No slot selected (or timed out).")
        return

    # slot_status was already set to Occupied by phone endpoint, but ensure consistency
    spot_status[slot_idx] = "Occupied"

    # generate exit QR for the slot (so it's also available in qr_codes/ folder)
    # exit QR encodes "Slot_X_QR" format so handle_exit (OpenCV decode) can interpret
    # generate simple Slot_N type QR (consistent with earlier logic)
    qr_path = generate_qr(slot_idx + 1)

    print(f"🅿 Car parked in Slot {slot_idx + 1}. Exit QR saved at: {qr_path}")
    # update laptop layout display briefly
    show_layout(wait_ms=1500)


# ---------- Main loop ----------
def main():
    while True:
        print("\n=== Indoor Smart Parking System ===")
        print("1. Car Entry")
        print("2. Car Exit (scan QR image)")
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