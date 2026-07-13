import cv2
from ultralytics import YOLO

# -----------------------------
# Load YOLOv11 model
# -----------------------------
model = YOLO("yolo11n.pt")  # Make sure this file is in the same folder

# -----------------------------
# Video source
# -----------------------------
video_path = "traffic.mp4"  # Make sure this file is in the same folder
cap = cv2.VideoCapture(video_path)

# -----------------------------
# Tracking setup
# -----------------------------
trackers = cv2.legacy.MultiTracker_create()  # Multiple trackers for multiple cars
car_count = 0
line_position = 400  # y-position for counting line

# Colors
green = (0, 255, 0)
red = (0, 0, 255)

# -----------------------------
# Main loop
# -----------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    # YOLO detection every few frames
    results = model.predict(frame, imgsz=384, conf=0.4)  # adjust confidence

    boxes = []
    for r in results:
        for box in r.boxes.xyxy:  # xyxy format
            x1, y1, x2, y2 = map(int, box)
            boxes.append((x1, y1, x2-x1, y2-y1))  # x, y, w, h

    # Initialize trackers for new detections
    if len(trackers.getObjects()) == 0 and boxes:
        for b in boxes:
            tracker = cv2.legacy.TrackerCSRT_create()
            trackers.add(tracker, frame, b)

    # Update trackers
    success, boxes = trackers.update(frame)

    # Draw boxes
    for i, box in enumerate(boxes):
        x, y, w, h = map(int, box)
        cv2.rectangle(frame, (x, y), (x+w, y+h), green, 2)

        # Count cars crossing the line
        if y+h > line_position:
            car_count += 1
            trackers.getObjects().pop(i)  # remove counted car

    # Draw counting line
    cv2.line(frame, (0, line_position), (frame.shape[1], line_position), red, 2)
    cv2.putText(frame, f"Cars: {car_count}", (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)

    # Display
    cv2.imshow("Traffic Monitor", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()
