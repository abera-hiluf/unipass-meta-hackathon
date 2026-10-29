from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProcessingResult:
    status: str
    reason_code: str


class DocumentProcessingStage(Protocol):
    def process(self, object_key: str) -> ProcessingResult: ...


class NotImplementedProcessingStage:
    """Placeholder for a future isolated processing worker or provider."""

    def process(self, object_key: str) -> ProcessingResult:
        return ProcessingResult(status="NOT_IMPLEMENTED", reason_code="processing_stage_not_configured")


class ImageQualityValidationStage(NotImplementedProcessingStage):
    pass


class DocumentRegionDetectionStage(NotImplementedProcessingStage):
    pass


class OcrExtractionStage(NotImplementedProcessingStage):
    pass


class PortraitExtractionStage(NotImplementedProcessingStage):
    pass
