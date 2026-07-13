import cv2
import numpy as np
import qrcode
import os
import time

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
        print(f"⚠ QR already exists for Slot {slot_id}. Skipping generation.")
        return qr_filename
    qr_data = f"Slot_{slot_id}_QR"
    qr_img = qrcode.make(qr_data)
    qr_img.save(qr_filename)
    print(f"🟩 QR saved: {qr_filename}")
    return qr_filename

# ---- NEW: minimal layout QR generator & displayer ----
def generate_layout_qr(display_time_ms=2000):
    """Generate and display a layout-access QR (minimal addition)."""
    qr_path = os.path.join(QR_FOLDER, "layout_qr.png")
    if not os.path.exists(qr_path):
        qr_img = qrcode.make("Layout_Access_QR")
        qr_img.save(qr_path)
        # print only once
        print("🟩 Layout access QR generated.")
    else:
        # QR already exists
        print("⚠ Layout QR already exists.")

    # load and display QR full-screen briefly
    qr_img_cv = cv2.imread(qr_path)
    if qr_img_cv is None:
        print("❌ Failed to load generated layout QR image.")
        return
    # build a white background and place QR centered (keeps consistent fullscreen look)
    h_win, w_win = 720, 1280
    bg = np.ones((h_win, w_win, 3), dtype=np.uint8) * 255
    # resize QR to fit (keep square)
    qr_size = 400
    qr_resized = cv2.resize(qr_img_cv, (qr_size, qr_size))
    y_offset = (h_win - qr_size) // 2
    x_offset = (w_win - qr_size) // 2
    bg[y_offset:y_offset+qr_size, x_offset:x_offset+qr_size] = qr_resized
    # message
    cv2.putText(bg, "📱 Scan this QR to access parking layout", (80, 100),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)

    cv2.namedWindow("Layout QR", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Layout QR", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("Layout QR", bg)
    cv2.waitKey(display_time_ms)  # milliseconds
    cv2.destroyWindow("Layout QR")
# -----------------------------------------------------


def draw_layout_image():
    """Return current layout image with slot colors."""
    img = layout_img.copy()
    for i, poly in enumerate(spots):
        color = (0, 255, 0) if spot_status[i] == "Free" else (0, 0, 255)
        cv2.polylines(img, [np.array(poly, np.int32)], True, color, 2)
        cv2.putText(img, str(i+1), tuple(poly[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
    return img


def show_layout(wait_ms=0):
    img = draw_layout_image()
    cv2.namedWindow("Parking Layout", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Parking Layout", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
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
    cv2.setWindowProperty("Car Entry", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
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
    cv2.putText(msg, "🚗 Please select a slot to park your vehicle", (80, 360),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
    cv2.imshow("Car Entry", msg)
    cv2.waitKey(2000)
    cv2.destroyWindow("Car Entry")


def select_parking_slot():
    selected = [None]

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        for i, poly in enumerate(spots):
            if cv2.pointPolygonTest(np.array(poly, np.int32), (x, y), False) >= 0:
                if spot_status[i] == "Free":
                    selected[0] = i
                    print(f"✅ Slot {i+1} selected.")
                    cv2.destroyAllWindows()
                else:
                    print(f"⚠ Slot {i+1} is occupied. Choose another.")
                return

    img = draw_layout_image()
    cv2.namedWindow("Select Slot", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Select Slot", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.setMouseCallback("Select Slot", on_click)
    while selected[0] is None:
        cv2.imshow("Select Slot", img)
        if cv2.waitKey(50) & 0xFF == 27:
            break
    cv2.destroyAllWindows()
    return selected[0]


# ---------- Robust handle_exit implementation ----------
def handle_exit():
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

    # 1) if numeric and in range -> take that index
    if raw.isdigit():
        n = int(raw)
        if 1 <= n <= len(qr_files):
            chosen_path = os.path.join(QR_FOLDER, qr_files[n-1])
        else:
            # maybe user typed slot number e.g. "3" meaning slot_3.png
            alt_name = f"slot_{n}.png"
            if alt_name in qr_files:
                chosen_path = os.path.join(QR_FOLDER, alt_name)

    # 2) if not resolved, check exact filename within the folder
    if not chosen_path:
        candidate = raw
        cand_in_folder = os.path.join(QR_FOLDER, candidate)
        if os.path.isfile(cand_in_folder):
            chosen_path = cand_in_folder
        elif os.path.isabs(candidate) and os.path.isfile(candidate):
            chosen_path = candidate

    # 3) fallback: try to extract digits from input and match slot_X
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

    # Display QR image fullscreen (simulate scanning)
    qr_img = cv2.imread(chosen_path)
    if qr_img is None:
        print("❌ Failed to open the chosen QR image.")
        return

    cv2.namedWindow("QR Scanner", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("QR Scanner", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("QR Scanner", qr_img)
    cv2.waitKey(1200)

    # Decode QR using OpenCV QRCodeDetector
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

    # parse slot id
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
    # show updated layout briefly
    show_layout(wait_ms=1500)


# ---------- Entry / Exit handlers ----------
def handle_entry():
    play_entry_video()

    # NEW: show layout access QR first (minimal and only addition)
    generate_layout_qr()  # <<< added here

    slot_idx = select_parking_slot()
    if slot_idx is None:
        print("❌ No slot selected.")
        return
    if spot_status[slot_idx] == "Occupied":
        print("⚠ That slot is already occupied.")
        return
    spot_status[slot_idx] = "Occupied"
    generate_qr(slot_idx + 1)
    print(f"🅿 Car parked in Slot {slot_idx + 1}.")
    show_layout(wait_ms=1000)


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