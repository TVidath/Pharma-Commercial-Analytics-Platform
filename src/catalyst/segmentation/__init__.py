"""Customer segmentation: doctors (Potential x Value 9-box) and hospitals (tiers)."""
from .doctors import segment_doctors, validate_with_kmeans
from .hospitals import segment_hospitals
from .report import build_report, persist_to_db

__all__ = ["segment_doctors", "segment_hospitals", "validate_with_kmeans",
           "build_report", "persist_to_db"]
