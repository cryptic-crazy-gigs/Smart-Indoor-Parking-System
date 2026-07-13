import cv2
import numpy as np

# -------- SETTINGS --------
IMAGE_PATH = "layout.png"  # Your layout image
OUTPUT_FILE = "parking_spots.npy"
# ---------------------------

# Load image
image = cv2.imread(IMAGE_PATH)
if image is None:
    print("❌ Could not load layout image.")
    exit()

spots = []
current = []
display = image.copy()

def mouse(event, x, y, flags, param):
    global current, spots, display
    if event == cv2.EVENT_LBUTTONDOWN:
        current.append((x, y))
        cv2.circle(display, (x, y), 4, (0, 255, 0), -1)
    elif event == cv2.EVENT_RBUTTONDOWN and len(current) >= 3:
        spots.append(np.array(current, np.int32))
        cv2.polylines(display, [np.array(current, np.int32)], True, (255, 0, 0), 2)
        current = []

cv2.namedWindow("Mark Slots", cv2.WINDOW_NORMAL)
cv2.setMouseCallback("Mark Slots", mouse)

print("🟢 Left-click to mark corners of slot.")
print("🔵 Right-click to close a slot polygon.")
print("✅ Press ENTER when done to save.")

while True:
    cv2.imshow("Mark Slots", display)
    key = cv2.waitKey(1)
    if key == 13:  # ENTER key
        break

cv2.destroyAllWindows()

# Save all slots
np.save(OUTPUT_FILE, spots, allow_pickle=True)
print(f"✅ Saved {len(spots)} parking slots to {OUTPUT_FILE}")