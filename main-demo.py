import cv2
import numpy as np
import qrcode
import os
import uuid
from PIL import Image

# ---------- INITIAL SETUP ----------
spots = np.load("parking_spots.npy", allow_pickle=True)
slots_status = {i: "free" for i in range(len(spots))}
os.makedirs("qr_codes", exist_ok=True)

layout = cv2.imread("layout.png")

# ---------- QR GENERATION ----------
def generate_qr(slot_id, car_id):
    unique_id = str(uuid.uuid4())[:8]
    data = f"Car {car_id} | Slot {slot_id + 1} | Exit Code: {unique_id}"
    qr = qrcode.make(data)
    file_path = os.path.join("qr_codes", f"car_{car_id}slot{slot_id + 1}_{unique_id}.png")
    qr.save(file_path)
    return file_path, data

# ---------- LAYOUT DRAWING ----------
def draw_layout():
    img = layout.copy()
    for i, s in enumerate(spots):
        polygon = np.array(s, np.int32).reshape((-1, 1, 2))
        color = (0, 255, 0) if slots_status[i] == "free" else (0, 0, 255)
        cv2.polylines(img, [polygon], True, color, 3)
        cv2.putText(img, str(i + 1), (polygon[0][0][0], polygon[0][0][1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return img

# ---------- SLOT SELECTION ----------
selected_slot = None
car_id = 1

def select_slot(event, x, y, flags, param):
    global selected_slot, car_id
    if event == cv2.EVENT_LBUTTONDOWN:
        for i, s in enumerate(spots):
            polygon = np.array(s, np.int32)
            result = cv2.pointPolygonTest(polygon, (x, y), False)
            if result >= 0 and slots_status[i] == "free":
                slots_status[i] = "occupied"
                qr_path, qr_data = generate_qr(i, car_id)
                print(f"\n🚗 Car {car_id} selected Slot {i + 1}")
                print(f"📱 Exit QR: {qr_data}")
                print(f"🖼 Saved QR at: {qr_path}")
                
                # Display QR for demonstration
                qr_img = Image.open(qr_path)
                qr_img.show()
                
                car_id += 1
                break

# ---------- ENTRY VIDEO SIMULATION ----------
def play_entry_video(label):
    cap = cv2.VideoCapture("indoor_parking.mp4")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        text = f"Car {label} Entering..."
        cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
        cv2.imshow("Car Entry", frame)
        if cv2.waitKey(30) == 27:
            break
    cap.release()
    cv2.destroyWindow("Car Entry")

# ---------- MAIN SIMULATION ----------
while True:
    print("\n========== SMART PARKING SYSTEM ==========")
    print("1️⃣ Simulate Car Entry (Auto for 2 Cars)")
    print("2️⃣ Simulate Car Exit")
    print("3️⃣ Exit Program")
    choice = input("Enter choice: ")

    if choice == "1":
        # Simulate 2 cars entering one after another
        for label in [1, 2]:
            play_entry_video(label)
            print(f"\n🅿 Layout opened for Car {label} — click on a slot to park.")
            cv2.namedWindow(f"Parking Layout - Car {label}")
            cv2.setMouseCallback(f"Parking Layout - Car {label}", select_slot)

            while True:
                layout_img = draw_layout()
                cv2.imshow(f"Parking Layout - Car {label}", layout_img)
                key = cv2.waitKey(1)
                if key == 27:  # ESC to stop selecting
                    cv2.destroyWindow(f"Parking Layout - Car {label}")
                    break

    elif choice == "2":
        print("Enter slot number to free:")
        try:
            num = int(input("Slot no: ")) - 1
            if 0 <= num < len(spots) and slots_status[num] == "occupied":
                slots_status[num] = "free"
                print(f"✅ Slot {num + 1} is now free!")
            else:
                print("⚠ Invalid slot or already free.")
        except ValueError:
            print("Invalid input.")

    elif choice == "3":
        print("👋 Exiting simulation...")
        break

cv2.destroyAllWindows()