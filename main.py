import cv2
import numpy as np
import qrcode
import os
import uuid

# Load parking spots
spots = np.load("parking_spots.npy", allow_pickle=True)
slots_status = {i: "free" for i in range(len(spots))}

# Create folder for QR codes
os.makedirs("qr_codes", exist_ok=True)

# Load layout
layout = cv2.imread("layout.png")

# Generate a unique QR code for a given slot
def generate_qr(slot_id):
    unique_id = str(uuid.uuid4())[:8]
    data = f"Slot {slot_id + 1} | Exit Code: {unique_id}"
    qr = qrcode.make(data)
    file_path = os.path.join("qr_codes", f"slot_{slot_id + 1}_{unique_id}.png")
    qr.save(file_path)
    return file_path, data

# Draw parking layout with colors
def draw_layout():
    img = layout.copy()
    for i, s in enumerate(spots):
        polygon = np.array(s, np.int32).reshape((-1, 1, 2))
        color = (0, 255, 0) if slots_status[i] == "free" else (0, 0, 255)
        cv2.polylines(img, [polygon], True, color, 3)
        cv2.putText(img, str(i + 1), (polygon[0][0][0], polygon[0][0][1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
    return img

# Mouse click event to select slot
def select_slot(event, x, y, flags, param):
    global selected_slot
    if event == cv2.EVENT_LBUTTONDOWN:
        for i, s in enumerate(spots):
            polygon = np.array(s, np.int32)
            result = cv2.pointPolygonTest(polygon, (x, y), False)
            if result >= 0 and slots_status[i] == "free":
                slots_status[i] = "occupied"
                qr_path, qr_data = generate_qr(i)
                print(f"🅿 Slot {i + 1} booked!")
                print(f"📱 Exit QR generated → {qr_data}")
                print(f"🖼 Saved at: {qr_path}")
                break

# Simulate car entry video
def play_entry_video():
    cap = cv2.VideoCapture("indoor_parking.mp4")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.imshow("Car Entry", frame)
        if cv2.waitKey(30) == 27:
            break
    cap.release()
    cv2.destroyWindow("Car Entry")

# Main demonstration loop
while True:
    print("\n--- SMART PARKING DEMO ---")
    print("1️⃣ Simulate Car Entry")
    print("2️⃣ Simulate Car Exit")
    print("3️⃣ Exit Demo")
    choice = input("Enter choice: ")

    if choice == "1":
        play_entry_video()
        cv2.namedWindow("Parking Layout")
        cv2.setMouseCallback("Parking Layout", select_slot)
        while True:
            layout_img = draw_layout()
            cv2.imshow("Parking Layout", layout_img)
            key = cv2.waitKey(1)
            if key == 27:  # ESC to go back
                cv2.destroyWindow("Parking Layout")
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
        print("Exiting demo...")
        break

cv2.destroyAllWindows()