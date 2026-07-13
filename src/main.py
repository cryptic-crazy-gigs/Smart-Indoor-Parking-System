import cv2
from ultralytics import YOLO

# Load YOLO model (replace with your model path if needed)
model = YOLO('yolov8n.pt')  # Using small YOLOv8 pre-trained model

# Open video or webcam
cap = cv2.VideoCapture(0)  # 0 for webcam, or 'data/videos/traffic.mp4'

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Make prediction
    results = model(frame)

    # Draw results
    annotated_frame = results[0].plot()

    cv2.imshow("Traffic Detection", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
