import threading
import re
from typing import Protocol

import numpy as np
from PIL import Image, ImageOps, ImageEnhance

from .config import settings
from .extraction import checking_header_fragments
from .schemas import Evidence


class OCREngine(Protocol):
    def read(self, pages: list[Image.Image]) -> list[Evidence]: ...
    def read_checking_barcode(self, page: Image.Image, evidence: list[Evidence]) -> Evidence | None: ...
    def read_quantity_plan_cs(self, page: Image.Image, evidence: list[Evidence]) -> Evidence | None: ...


class PaddleEngine:
    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()

    def read(self, pages: list[Image.Image]) -> list[Evidence]:
        # Paddle predictors are shared only within a serialized inference section.
        with self._lock:
            if self._engine is None:
                from paddleocr import PaddleOCR
                # Setting an explicit detector bypasses PaddleOCR's lang-to-model
                # selection, so pin the Thai recognizer too. It reads Thai, English,
                # and digits in one pass, keeping mixed-language OCR fast.
                recognition_models = {"th": "th_PP-OCRv5_mobile_rec"}
                recognition_model = recognition_models.get(settings().ocr_lang)
                if recognition_model is None:
                    raise ValueError(f"Unsupported OCR_LANG: {settings().ocr_lang}; use th")
                self._engine = PaddleOCR(text_detection_model_name="PP-OCRv5_mobile_det",
                                         text_recognition_model_name=recognition_model,
                                         text_det_limit_side_len=1280, text_det_limit_type="max",
                                         device="cpu", enable_mkldnn=False, cpu_threads=4,
                                         use_doc_orientation_classify=False,
                                         use_doc_unwarping=False, use_textline_orientation=False)
            lines = []
            for page_number, page in enumerate(pages, 1):
                # Paddle takes BGR ndarray input.
                for result in self._engine.predict(np.asarray(page)[:, :, ::-1].copy()):
                    for text, score, polygon in zip(result["rec_texts"], result["rec_scores"], result["rec_polys"]):
                        lines.append(Evidence(text=str(text), confidence=float(score),
                                              page=page_number, box=polygon.tolist()))
            return lines

    def split_checking_cells(self, page: Image.Image, evidence: list[Evidence]) -> list[Evidence]:
        """Use detected table rules to re-read fused header cells individually."""
        import cv2
        from .extraction import bounds

        fused = [v for v in evidence if v.page == 1 and v.box
                 and len(re.findall(r"(?:Plan|Rec)\s*\(", v.text, re.I)) > 1]
        if not fused:
            return evidence
        gray = cv2.cvtColor(np.asarray(page.convert('RGB')), cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        segments = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=35,
                                  minLineLength=max(30, page.width // 35), maxLineGap=15)
        if segments is None:
            return evidence
        output = list(evidence)
        for row in fused:
            left, top, right, bottom = bounds(row)
            height = max(bottom - top, 1)
            cy = (top + bottom) / 2
            vertical = []
            for x1, y1, x2, y2 in segments[:, 0]:
                if abs(y2-y1) > abs(x2-x1)*5 and min(y1,y2)-height*.3 <= cy <= max(y1,y2)+height*.3:
                    x = x1 + (cy-y1)*(x2-x1)/(y2-y1)
                    if left-height <= x <= right+height:
                        vertical.append(float(x))
            borders = []
            for x in sorted(vertical):
                if not borders or x-borders[-1] > height*.2:
                    borders.append(x)
            cells = [(a,b) for a,b in zip(borders,borders[1:]) if b-a > height*.65
                     and a < right and b > left]
            expected = len(re.findall(r"(?:Plan|Rec)\s*\(", row.text, re.I))
            if len(cells) != expected:
                continue
            replacements = []
            removed = [row]
            for a,b in cells:
                quantities = [v for v in evidence if v.page == row.page and v.box
                              and v.text.strip().lower() == 'quantity'
                              and a < (bounds(v)[0]+bounds(v)[2])/2 < b
                              and top-height*2 < bounds(v)[1] < bottom]
                header_top = min([bounds(v)[1] for v in quantities] or [top])
                crop_box = (max(0,int(a+3)), max(0,int(header_top-2)), min(page.width,int(b-3)), min(page.height,int(bottom+2)))
                crop = page.crop(crop_box)
                normalized = ImageOps.autocontrast(crop.convert('L')).convert('RGB')
                enlarged = normalized.resize((normalized.width*3,normalized.height*3),Image.Resampling.LANCZOS)
                try:
                    readings = self.read([enlarged])
                finally:
                    crop.close(); normalized.close(); enlarged.close()
                text = ' '.join(v.text for v in readings)
                match = re.search(r'(Plan|Rec)\s*\(\s*(CS|MU)\s*\)',text,re.I)
                if not match:
                    break
                label = f'Quantity {match[1].title()} ({match[2].upper()})'
                replacements.append(Evidence(text=label, confidence=min(v.confidence for v in readings),page=row.page,
                    box=[[a,header_top],[b,header_top],[b,bottom],[a,bottom]]))
                removed.extend(quantities)
            if len(replacements) == expected:
                output = [v for v in output if v not in removed] + replacements
        return output

    def read_quantity_plan_cs(self, page: Image.Image, evidence: list[Evidence]) -> Evidence | None:
        """OCR only the Checksheet Quantity Plan (CS) value when layout OCR fused its headers."""
        candidates = evidence + checking_header_fragments(evidence)
        headers = [line for line in candidates if line.page == 1 and line.box
                   and re.search(r"Plan\s*\(\s*CS\s*\)", line.text, re.I)]
        combined = [line for line in headers if re.match(r"Quantity\s+Plan\s*\(\s*CS\s*\)", line.text, re.I)]
        if combined:
            headers = combined
        if not headers:
            return None
        header = max(headers, key=lambda line: line.confidence)
        hx = [point[0] for point in header.box]; hy = [point[1] for point in header.box]
        left, right, top, bottom = min(hx), max(hx), min(hy), max(hy)
        header_height = max(bottom - top, 1)
        quantities = []
        for line in evidence:
            if line.page != header.page or not line.box or line.text.strip().casefold() != "quantity":
                continue
            xs = [point[0] for point in line.box]; ys = [point[1] for point in line.box]
            center_x = (min(xs) + max(xs)) / 2
            center_y = (min(ys) + max(ys)) / 2
            if left <= center_x <= right and top - header_height * 1.6 <= center_y <= bottom:
                quantities.append((center_x, min(xs), max(xs), min(ys), max(ys)))
        if not quantities:
            if re.fullmatch(r'Quantity\s+Plan\s*\(CS\)', header.text, re.I):
                quantities = [((left+right)/2,left,right,top,bottom)]
                header_height = max(header_height / 2, 1)
            else:
                return None
        quantities.sort()
        center, label_left, label_right, _, _ = quantities[0]
        next_gap = quantities[1][0] - center if len(quantities) > 1 else (label_right - label_left) * 1.7
        half_width = min(next_gap * 0.6, (label_right - label_left) * 0.62)
        crop_left = max(0, int(center - half_width))
        crop_right = min(page.width, int(center + half_width))
        crop_top = max(0, int(bottom - header_height * 0.18))
        crop_bottom = min(page.height, int(bottom + header_height * 1.05))
        if crop_right - crop_left < 24 or crop_bottom - crop_top < 24:
            return None
        scale = 4
        crop = page.crop((crop_left, crop_top, crop_right, crop_bottom))
        normalized = ImageOps.autocontrast(crop.convert("L")).convert("RGB")
        enlarged = normalized.resize((normalized.width * scale, normalized.height * scale), Image.Resampling.LANCZOS)
        try:
            readings = self.read([enlarged])
        finally:
            crop.close()
            normalized.close()
            enlarged.close()
        numbers = [line for line in readings if re.fullmatch(r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", line.text.strip())]
        if len(numbers) != 1:
            return None
        number = numbers[0]
        translated = [[crop_left + point[0] / scale, crop_top + point[1] / scale] for point in number.box]
        return Evidence(text=number.text.strip(), confidence=number.confidence,
                        page=header.page, box=translated)

    def read_checking_barcode(self, page: Image.Image, evidence: list[Evidence]) -> Evidence | None:
        """Decode a Checksheet barcode, preferring the one next to its ASN/SN/PO label."""
        import zxingcpp

        decoded = zxingcpp.read_barcodes(np.asarray(page.convert("RGB")), try_rotate=True, try_downscale=True)
        valid = [code for code in decoded if code.text and 3 <= len(code.text) <= 100
                 and re.fullmatch(r"[A-Z0-9-]+", code.text, re.I)]
        if not valid:
            return None
        anchors = []
        for line in evidence:
            if not line.box or not re.search(r"\b(?:A?SN|PO|SRN)\s*No\b", line.text, re.I):
                continue
            xs = [point[0] for point in line.box]; ys = [point[1] for point in line.box]
            anchors.append((min(xs), min(ys), max(xs), max(ys)))
        selected = None
        if anchors:
            ranked = []
            for code in valid:
                points = [code.position.top_left, code.position.top_right,
                          code.position.bottom_right, code.position.bottom_left]
                box = (min(point.x for point in points), min(point.y for point in points),
                       max(point.x for point in points), max(point.y for point in points))
                for ax1, ay1, ax2, ay2 in anchors:
                    dx = max(0.0, ax1 - box[2], box[0] - ax2)
                    dy = max(0.0, ay1 - box[3], box[1] - ay2)
                    ranked.append((dx * dx + dy * dy, code, points))
            if ranked:
                distance, selected, points = min(ranked, key=lambda value: value[0])
                if distance ** 0.5 > max(page.size) * 0.15:
                    return None
        elif len(valid) == 1:
            selected = valid[0]
            points = [selected.position.top_left, selected.position.top_right,
                      selected.position.bottom_right, selected.position.bottom_left]
        else:
            return None
        return Evidence(text=selected.text, confidence=1.0, page=1,
                        box=[[float(point.x), float(point.y)] for point in points])


engine: OCREngine = PaddleEngine()
