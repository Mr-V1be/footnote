from __future__ import annotations

import io
import statistics
from collections import defaultdict
from dataclasses import dataclass

import anyio
import anyio.to_thread
import pytesseract
from PIL import Image

from footnote.ports.ocr import OcrLine, OcrPage

CONFIDENCE_SCALE = 100.0


@dataclass(frozen=True, slots=True)
class TesseractConfig:
    languages: str = "rus+eng"
    page_segmentation_mode: int = 3
    timeout_seconds: int = 180
    max_concurrency: int = 2


class TesseractOcrEngine:
    """Recognition with the Tesseract binary; CPU-bound work runs off the event loop."""

    def __init__(self, config: TesseractConfig) -> None:
        self._config = config
        self._limiter = anyio.CapacityLimiter(config.max_concurrency)

    async def recognize(self, image_png: bytes, *, dpi: int) -> OcrPage:
        return await anyio.to_thread.run_sync(
            self._recognize, image_png, dpi, limiter=self._limiter
        )

    def _recognize(self, image_png: bytes, dpi: int) -> OcrPage:
        with Image.open(io.BytesIO(image_png)) as image:
            width, height = image.size
            data = pytesseract.image_to_data(
                image,
                lang=self._config.languages,
                config=f"--psm {self._config.page_segmentation_mode} --dpi {dpi}",
                output_type=pytesseract.Output.DICT,
                timeout=self._config.timeout_seconds,
            )
        words: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for index, text in enumerate(data["text"]):
            confidence = float(data["conf"][index])
            if confidence < 0 or not str(text).strip():
                continue
            key = (
                int(data["block_num"][index]),
                int(data["par_num"][index]),
                int(data["line_num"][index]),
            )
            words[key].append(index)
        lines: list[OcrLine] = []
        for _, indices in sorted(words.items()):
            lefts = [int(data["left"][i]) for i in indices]
            tops = [int(data["top"][i]) for i in indices]
            rights = [int(data["left"][i]) + int(data["width"][i]) for i in indices]
            bottoms = [int(data["top"][i]) + int(data["height"][i]) for i in indices]
            lines.append(
                OcrLine(
                    text=" ".join(str(data["text"][i]).strip() for i in indices),
                    left=float(min(lefts)),
                    top=float(min(tops)),
                    right=float(max(rights)),
                    bottom=float(max(bottoms)),
                    height=float(max(bottoms) - min(tops)),
                    confidence=statistics.fmean(float(data["conf"][i]) for i in indices)
                    / CONFIDENCE_SCALE,
                )
            )
        return OcrPage(width=float(width), height=float(height), dpi=dpi, lines=tuple(lines))
