import cv2
import numpy as np
import qrcode
import os
import time
from datetime import datetime

# ---------------- SETTINGS ----------------
LAYOUT_FILE = "layout.png"
SPOTS_FILE = "parking_spots.npy"
VIDEO_FILE = "car_entry.mp4"
QR_FOLDER = "qr_codes"
os.makedirs(QR_FOLDER, exist_ok=True)
# ------------------------------------------

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

# Initialize spot status
spot_status = ["Free"] * len(spots)

# ---------- Helper Functions ----------
def generate_qr(slot_id):
    """Generate a QR code for a slot and save it."""
    qr_data = f"Slot_{slot_id}_QR"
    qr = qrcode.make(qr_data)
    qr_filename = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
    qr.save(qr_filename)
    print(f"🟩 QR generated and saved for Slot {slot_id}: {qr_filename}")

def show_layout(highlight_slot=None):
    """Display layout with slot status colors."""
    display = layout_img.copy()
    for i, polygon in enumerate(spots):
        color = (0, 255, 0) if spot_status[i] == "Free" else (0, 0, 255)
        cv2.polylines(display, [np.array(polygon, np.int32)], True, color, 2)
        cv2.putText(display, f"{i+1}", tuple(polygon[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
        if highlight_slot == i + 1:
            cv2.putText(display, "SELECTED", (polygon[0][0] + 40, polygon[0][1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

    cv2.namedWindow("Parking Layout", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Parking Layout", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    cv2.imshow("Parking Layout", display)
    return display

def play_entry_video():
    """Play entry video full screen and show message afterward."""
    cap = cv2.VideoCapture(VIDEO_FILE)
    if not cap.isOpened():
        print("⚠ Entry video not found or can't open.")
        return

    screen_w, screen_h = 1280, 720
    cv2.namedWindow("Car Entry", cv2.WINDOW_NORMAL)
    cv2.setWindowProperty("Car Entry", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        h, w = frame.shape[:2]
        scale = min(screen_w / w, screen_h / h)
        frame_resized = cv2.resize(frame, (int(w * scale), int(h * scale)))
        cv2.imshow("Car Entry", frame_resized)
        if cv2.waitKey(25) & 0xFF == 27:
            break

    cap.release()

    # After video ends → show message screen
    msg_img = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.putText(msg_img, "🚗 Please select a slot to park your vehicle",
                (100, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 0), 3)
    cv2.imshow("Car Entry", msg_img)
    cv2.waitKey(2000)
    cv2.destroyWindow("Car Entry")

def select_parking_slot():
    """Allow user to select ONE slot using mouse."""
    selected = [None]

    def click_event(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            for i, polygon in enumerate(spots):
                if cv2.pointPolygonTest(np.array(polygon, np.int32), (x, y), False) >= 0:
                    if spot_status[i] == "Free":
                        selected[0] = i
                        print(f"✅ Slot {i + 1} selected.")
                    else:
                        print("❌ Slot already occupied.")
            if selected[0] is not None:
                cv2.destroyAllWindows()

    display = show_layout()
    cv2.setMouseCallback("Parking Layout", click_event)

    while True:
        cv2.imshow("Parking Layout", display)
        if selected[0] is not None or cv2.waitKey(1) & 0xFF == 27:
            break
    cv2.destroyAllWindows()
    return selected[0]

def handle_entry():
    play_entry_video()
    slot_id = select_parking_slot()
    if slot_id is None:
        print("❌ No slot selected.")
        return
    spot_status[slot_id] = "Occupied"
    generate_qr(slot_id + 1)
    print(f"🅿 Car parked in Slot {slot_id + 1}.\n")

def handle_exit():
    occupied_slots = [i + 1 for i, s in enumerate(spot_status) if s == "Occupied"]
    if not occupied_slots:
        print("🟨 No occupied slots currently.")
        return

    print("\nOccupied Slots:", occupied_slots)
    slot_id = int(input("Enter Slot Number to Exit: "))
    if slot_id in occupied_slots:
        qr_path = os.path.join(QR_FOLDER, f"slot_{slot_id}.png")
        if os.path.exists(qr_path):
            os.remove(qr_path)
        spot_status[slot_id - 1] = "Free"
        print(f"🚗 Car exited from Slot {slot_id}. QR deleted.\n")
    else:
        print("❌ Invalid slot number.")

def view_layout():
    """Show current parking layout."""
    show_layout()
    cv2.waitKey(0)
    cv2.destroyAllWindows()

# ---------- MAIN LOOP ----------
def main():
    while True:
        print("\n====== Indoor Smart Parking System ======")
        print("1. Car Entry")
        print("2. Car Exit")
        print("3. View Parking Layout")
        print("4. Exit Program")
        choice = input("Enter choice: ")

        if choice == "1":
            handle_entry()
        elif choice == "2":
            handle_exit()
        elif choice == "3":
            view_layout()
        elif choice == "4":
            print("👋 Exiting program.")
            break
        else:
            print("❌ Invalid choice.")

if __name__ == "__main__":
    main()