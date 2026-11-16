"""Yuz aniqlash dvigateli (InsightFace). Ogʻir kutubxonalar faqat birinchi chaqiruvda yuklanadi.

Dvigatel rasmdan har bir yuz uchun normalizatsiya qilingan vektor (embedding) va bosh burilishi
(yaw, daraja) qaytaradi. Rasm saqlanmaydi. Oʻrnatish: ``pip install -r requirements-face.txt``.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Protocol, Sequence

logger = logging.getLogger(__name__)


class FaceEngineUnavailable(RuntimeError):
    """InsightFace/onnxruntime oʻrnatilmagan yoki model yuklanmadi."""


@dataclass(frozen=True)
class FaceReading:
    embedding: tuple[float, ...]  # birlik uzunlikdagi vektor
    yaw: float                    # daraja; 0 — toʻgʻri qarash


class FaceEngine(Protocol):
    def analyze(self, image: bytes) -> Sequence[FaceReading]: ...


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Birlik vektorlar uchun kosinus oʻxshashligi."""
    if len(a) != len(b) or not a:
        return -1.0
    return float(sum(x * y for x, y in zip(a, b)))


class InsightFaceEngine:
    def __init__(self, model: str = "buffalo_l") -> None:
        self._model = model
        self._app = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._app is not None:
                return self._app
            try:
                from insightface.app import FaceAnalysis
            except ImportError as exc:
                raise FaceEngineUnavailable("insightface oʻrnatilmagan") from exc
            app = FaceAnalysis(name=self._model, providers=["CPUExecutionProvider"],
                               allowed_modules=["detection", "recognition", "landmark_3d_68"])
            app.prepare(ctx_id=-1, det_size=(640, 640))
            self._app = app
            return app

    def analyze(self, image: bytes) -> Sequence[FaceReading]:
        import cv2
        import numpy as np

        app = self._load()
        frame = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            return []
        readings = []
        for face in app.get(frame):
            pose = getattr(face, "pose", None)
            yaw = float(pose[1]) if pose is not None else 0.0
            readings.append(FaceReading(tuple(float(x) for x in face.normed_embedding), yaw))
        return readings


_engine: FaceEngine | None = None


def get_engine() -> FaceEngine:
    global _engine
    if _engine is None:
        _engine = InsightFaceEngine()
    return _engine


def set_engine(engine: FaceEngine | None) -> None:
    """Testlar uchun almashtirish."""
    global _engine
    _engine = engine
