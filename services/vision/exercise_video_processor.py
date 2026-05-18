import os
import cv2
import av
import numpy as np
import mediapipe as mp
import threading

from streamlit_webrtc import VideoProcessorBase
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from detectors.squat import SquatDetector
from detectors.pushup import PushUpDetector
from detectors.biceps_curl import BicepsCurlDetector
from detectors.shoulder_press import ShoulderPressDetector
from detectors.lunges import LungesDetector

from services.config.workout_config import POSE_CONNECTIONS


class VideoProcessorClass(VideoProcessorBase):

    def __init__(self):
        self._lock = threading.Lock()
        self._latest_metrics = {}
        self._exercise_type = "Squats"

        model_path = os.path.join(os.getcwd(), "ml_models", "pose_landmarker_full.task")

        base_option = python.BaseOptions(model_asset_path=model_path)

        options = vision.PoseLandmarkerOptions(
            base_options=base_option,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.7,
            min_pose_presence_confidence=0.7,
            min_tracking_confidence=0.7
        )

        self._landmarker = vision.PoseLandmarker.create_from_options(options)

        self._detectors = {
            "Squats": SquatDetector(),
            "Push-ups": PushUpDetector(),
            "Biceps Curls (Dumbbell)": BicepsCurlDetector(),
            "Shoulder Press": ShoulderPressDetector(),
            "Lunges": LungesDetector(),
        }

        self._timestamp_ms = 0

    def set_exercise(self, exercise_type):
        with self._lock:
            self._exercise_type = exercise_type

    def get_exercise(self):
        with self._lock:
            return self._exercise_type

    def set_latest_metrics(self, metrics):
        with self._lock:
            self._latest_metrics = dict(metrics)

    def get_latest_metrics(self):
        with self._lock:
            return dict(self._latest_metrics) if self._latest_metrics else None

    def _draw_skeleton(self, img, landmarks):
        h, w = img.shape[:2]

        for start_idx, end_idx in POSE_CONNECTIONS:
            p1 = landmarks[start_idx]
            p2 = landmarks[end_idx]

            if p1.visibility > 0.7 and p2.visibility > 0.7:
                cv2.line(img,
                         (int(p1.x * w), int(p1.y * h)),
                         (int(p2.x * w), int(p2.y * h)),
                         (0, 255, 0), 6)

        for lm in landmarks:
            if lm.visibility > 0.7:
                cv2.circle(img,
                           (int(lm.x * w), int(lm.y * h)),
                           6, (255, 0, 0), -1)

    def _draw_no_pose(self, img):
        cv2.putText(img, "NO POSE DETECTED", (30, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    def _draw_overlay(self, img, metrics, ex_type):
        h, _ = img.shape[:2]

        if ex_type == "Squats":
            cv2.putText(img, f"DEPTH: {metrics.get('depth_status','')}",
                        (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        elif ex_type == "Push-ups":
            cv2.putText(img,
                        f"BODY: {metrics.get('body_alignment','')} | HIP: {metrics.get('hip_status','')}",
                        (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        elif ex_type == "Biceps Curls (Dumbbell)":
            cv2.putText(img,
                        f"SWING: {metrics.get('swing_status','')}",
                        (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    def recv(self, frame):

        image = cv2.flip(frame.to_ndarray(format="bgr24"), 1)

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb
        )

        self._timestamp_ms += 33

        result = self._landmarker.detect_for_video(mp_image, self._timestamp_ms)

        ex_type = self.get_exercise()
        detector = self._detectors.get(ex_type)

        if result.pose_landmarks:

            landmarks = result.pose_landmarks[0]

            self._draw_skeleton(image, landmarks)

            if detector:
                metrics = detector.process(landmarks)

                if not metrics:
                    metrics = {}

                metrics["pose_detected"] = True

                self._draw_overlay(image, metrics, ex_type)

                self.set_latest_metrics(metrics)

        else:
            self._draw_no_pose(image)

            self.set_latest_metrics({
                "pose_detected": False
            })

        return av.VideoFrame.from_ndarray(image, format="bgr24")