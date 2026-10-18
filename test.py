from ultralytics import YOLO
import cv2

model = YOLO('data/models/yolov8n.pt')  # downloads weights automatically first run

cap = cv2.VideoCapture('data/samples/test_clip.webm')
ret, frame = cap.read()

results = model(frame, classes=[2, 3, 5, 7], conf=0.5)  # car, motorcycle, bus, truck
annotated = results[0].plot()  # draws boxes on the frame
cv2.imwrite('detection_check.jpg', annotated)