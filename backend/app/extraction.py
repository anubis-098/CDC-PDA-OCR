"""Conservative rules; document content is always data, never executable instructions."""
import re

from .schemas import Evidence, Extracted, Item, Kind

NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
PO = re.compile(r"\b(PO\s*No\.?\s*(?:/\s*SRN\s*No\.?)?|A?SN\s*No\.?)\s*[:=]?\s*([A-Z0-9][A-Z0-9 -]*)$", re.I)
PLAN = re.compile(rf"Quantity\s+Plan\s*\((\w+)\)\s*[:=]?\s*({NUMBER})\b", re.I)
QTY = re.compile(rf"\bQTY\s*[:=]?\s*({NUMBER})\s+(?:UOM\s*[:=]?\s*)?([A-Z]{{1,10}})\b", re.I)
CODE = re.compile(r"(?:Material\s+Code|Item\s+Code|Barcode)\s*[:=]\s*([A-Z0-9-]+)", re.I)


def bounds(line: Evidence) -> tuple[float, float, float, float]:
    return (min(p[0] for p in line.box), min(p[1] for p in line.box),
            max(p[0] for p in line.box), max(p[1] for p in line.box))


def checking_header_fragments(lines: list[Evidence]) -> list[Evidence]:
    """Join vertically stacked Quantity / Plan (CS) OCR fragments into one header."""
    combined: list[Evidence] = []
    by_page: dict[int, list[Evidence]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)

    for page, page_lines in by_page.items():
        quantities = [line for line in page_lines if re.fullmatch(r"Quantity\s*[:=]?", line.text.strip(), re.I)]
        plans = [line for line in page_lines if re.fullmatch(r"Plan\s*\(\s*CS\s*\)\s*[:=]?", line.text.strip(), re.I)]
        for quantity in quantities:
            for plan in plans:
                if quantity.box and plan.box:
                    qx1, qy1, qx2, qy2 = bounds(quantity)
                    px1, py1, px2, py2 = bounds(plan)
                    qh, ph = max(qy2 - qy1, 1), max(py2 - py1, 1)
                    vertical_gap = max(0.0, max(qy1, py1) - min(qy2, py2))
                    qcenter, pcenter = (qx1 + qx2) / 2, (px1 + px2) / 2
                    if vertical_gap > max(qh, ph) * 1.5 or abs(qcenter - pcenter) > max(qx2 - qx1, px2 - px1) * 0.45:
                        continue
                    x1, y1, x2, y2 = min(qx1, px1), min(qy1, py1), max(qx2, px2), max(qy2, py2)
                    box = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                elif not quantity.box and not plan.box:
                    # OCR without coordinates can still join directly adjacent fragments.
                    page_order = [line for line in page_lines if not line.box]
                    try:
                        qi, pi = page_order.index(quantity), page_order.index(plan)
                    except ValueError:
                        continue
                    if abs(qi - pi) != 1:
                        continue
                    box = []
                else:
                    continue
                combined.append(Evidence(text="Quantity Plan (CS)",
                                         confidence=min(quantity.confidence, plan.confidence),
                                         page=page, box=box))
    return combined


def reading_lines(lines: list[Evidence]) -> list[Evidence]:
    """Group OCR fragments on the same baseline, keeping page boundaries."""
    output: list[Evidence] = []
    for page in sorted({line.page for line in lines}):
        positioned = [line for line in lines if line.page == page and line.box]
        groups: list[list[Evidence]] = []
        for line in sorted(positioned, key=lambda v: (bounds(v)[1], bounds(v)[0])):
            x1, y1, x2, y2 = bounds(line)
            for group in reversed(groups):
                _, gy1, _, gy2 = bounds(group[0])
                if abs((y1 + y2 - gy1 - gy2) / 2) <= min(y2 - y1, gy2 - gy1) * 0.45:
                    group.append(line)
                    break
            else:
                groups.append([line])
        for group in groups:
            group.sort(key=lambda v: bounds(v)[0])
            output.append(Evidence(text=" | ".join(v.text for v in group),
                                   confidence=min(v.confidence for v in group), page=page,
                                   box=group[0].box))
        output.extend(line for line in lines if line.page == page and not line.box)
    return output


def extract(lines: list[Evidence], kind: Kind, checking_cs_value: Evidence | None = None,
            checking_barcode: Evidence | None = None) -> Extracted:
    result = Extracted()
    # Original fragments first; also inspect spatially joined label/value pairs.
    split_headers = checking_header_fragments(lines) if kind == "checking" else []
    candidates = lines + reading_lines(lines) + split_headers
    refs: list[tuple[str, str, float]] = []
    for line in candidates:
        text = line.text.replace(" | ", " ").strip()
        match = PO.search(text)
        if match and (kind == "checking" or match[1].upper().startswith("PO")):
            refs.append((match[1], match[2].strip(), line.confidence))
    preferred = [r for r in refs if r[0].upper().startswith("PO")] or refs
    unique = {r[1] for r in preferred}
    if len(unique) == 1:
        label, value, confidence = max(preferred, key=lambda r: r[2])
        result.po, result.po_source, result.po_confidence = value, label, confidence
    elif len(unique) > 1:
        result.warnings.append("พบเลขอ้างอิงหลายค่า กรุณาเลือก PO ที่ถูกต้อง")
    if kind == "checking" and checking_barcode is not None and re.fullmatch(r"[A-Z0-9-]{3,100}", checking_barcode.text, re.I):
        result.po = checking_barcode.text
        result.po_source = "Barcode"
        result.po_confidence = checking_barcode.confidence
        result.warnings = [warning for warning in result.warnings if "พบเลขอ้างอิงหลายค่า" not in warning]

    # Extract from joined rows only to avoid counting a fragment twice.
    for line in lines:
        text = line.text.replace(" | ", " ")
        code = CODE.search(text)
        if kind == "checking":
            matches = list(PLAN.finditer(text))
            matches = [m for m in matches if m[1].upper() == "CS"] or matches
            if len(matches) > 1:
                result.warnings.append("พบจำนวนหลายหน่วยในแถวเดียว กรุณาตรวจรายการ")
            for m in matches:
                result.items.append(Item(code=code[1] if code else "", qty=m[2], uom=m[1].upper(),
                                         source=line.text, confidence=line.confidence))
        else:
            for m in QTY.finditer(text):
                result.items.append(Item(code=code[1] if code else "", qty=m[1], uom=m[2].upper(),
                                         source=line.text, confidence=line.confidence))
    if kind == "checking" and checking_cs_value is not None and re.fullmatch(NUMBER, checking_cs_value.text.strip()):
        result.items = [Item(qty=checking_cs_value.text.strip(), uom="CS",
                             source="Quantity Plan (CS) · OCR เฉพาะช่อง",
                             confidence=min(checking_cs_value.confidence,
                                            max((line.confidence for line in lines if re.search(r"Plan\s*\(\s*CS\s*\)", line.text, re.I)), default=checking_cs_value.confidence)))]
    elif kind == "checking" and any(item.uom == "CS" for item in result.items):
        result.items = [item for item in result.items if item.uom == "CS"]
    if not result.items:
        result.items = invoice_column_items(lines) if kind == "invoice" else table_candidates(lines + split_headers, kind)
        if result.items:
            result.warnings.append("ค่าจากตำแหน่งคอลัมน์เป็นข้อเสนอ กรุณาตรวจแถวสินค้าและยืนยันทั้งหมด")
        else:
            result.warnings.append("อ่านจำนวนจากตารางไม่ได้ กรุณาเพิ่มรายการจากเอกสาร")
    if len({line.page for line in lines}) > 1:
        result.warnings.append("เอกสารหลายหน้า กรุณาตรวจว่ารายการครบและไม่มีแถวรวมซ้ำ")
    if len(result.items) > 200:
        result.items = result.items[:200]
        result.warnings.append("เกิน 200 รายการ กรุณาแบ่งเอกสารและตรวจว่ารายการครบ")
    return result


def table_candidates(lines: list[Evidence], kind: Kind) -> list[Item]:
    """Suggest aligned table cells; never auto-pass a spatial guess."""
    positioned = [line for line in lines if line.box]
    items: list[Item] = []
    seen_cells = set()
    for header in positioned:
        label = re.sub(r"\s+", " ", header.text).strip()
        if kind == "checking":
            # A fused row spanning Plan(CS), Rec(CS), Plan(MU), and Rec(MU)
            # cannot identify a single value by its center. Let the targeted
            # cell OCR handle it instead of suggesting values from other units.
            if len(re.findall(r"Plan\s*\(\s*[A-Z]+\s*\)", label, re.I)) > 1:
                continue
            is_header = bool(re.search(r"(?:Quantity\s*)?Plan\s*\(CS\)", label, re.I))
        else:
            is_header = label.upper() == "QTY"
        if not is_header:
            continue
        hx1, hy1, hx2, hy2 = bounds(header)
        hh = max(hy2 - hy1, 1)
        for line in positioned:
            if line.page != header.page or not re.fullmatch(NUMBER, line.text.strip()):
                continue
            x1, y1, x2, y2 = bounds(line)
            if not (hy2 < y1 < hy2 + hh * 2.5 and hx1 - hh * 0.5 <= (x1 + x2) / 2 <= hx2 + hh * 0.5):
                continue
            unit = "CS" if kind == "checking" else ""
            confidence = min(header.confidence, line.confidence)
            if kind == "invoice":
                units = [v for v in positioned if v.page == line.page and re.fullmatch(r"[A-Z]{1,6}", v.text.strip())
                         and 0 <= bounds(v)[0] - x2 < hh * 5
                         and abs((bounds(v)[1] + bounds(v)[3] - y1 - y2) / 2) < hh]
                if len(units) == 1:
                    unit = units[0].text.strip()
                    confidence = min(confidence, units[0].confidence)
            cell_key = (line.page, tuple(map(tuple, line.box)))
            if cell_key in seen_cells:
                continue
            seen_cells.add(cell_key)
            items.append(Item(qty=line.text.strip(), uom=unit,
                              source=f"หน้า {line.page}: {header.text} → {line.text}", confidence=confidence))
    return items[:200]


def invoice_column_items(lines: list[Evidence]) -> list[Item]:
    """Associate data below QTY with UOM in the same data row, never prices."""
    positioned = [v for v in lines if v.box]
    output = []
    for header in positioned:
        if header.text.strip().upper() != "QTY":
            continue
        hx1, hy1, hx2, hy2 = bounds(header)
        hh = max(hy2-hy1, 1)
        unit_headers = [v for v in positioned if v.page == header.page
                        and re.match(r"^UOM\b", v.text.strip(), re.I)
                        and bounds(v)[0] >= hx2 - hh
                        and abs(bounds(v)[1]-hy1) < hh*1.5]
        if not unit_headers:
            continue
        uh = min(unit_headers, key=lambda v: bounds(v)[0])
        ux1, uy1, ux2, uy2 = bounds(uh)
        # A fused 'UOM Price per' header has its unit column at its left edge.
        unit_right = min(ux2, ux1 + max(hx2-hx1, hh*1.5))
        stop = min([bounds(v)[1] for v in positioned if v.page == header.page
                    and bounds(v)[1] > hy2 and re.search(r"Total|Discount|Tax Rate|Payment", v.text, re.I)]
                   or [hy2+hh*10])
        for value in positioned:
            if value.page != header.page:
                continue
            match = re.fullmatch(rf"({NUMBER})(?:\s+([A-Z]{{1,6}}))?", value.text.strip(), re.I)
            if not match:
                continue
            x1,y1,x2,y2 = bounds(value)
            if not (hy2 < y1 < stop and hx1-hh <= x1 < ux1):
                continue
            unit = match[2]
            confidence = min(header.confidence,value.confidence)
            if not unit:
                units = [v for v in positioned if v.page == header.page
                         and re.fullmatch(r"[A-Z]{1,6}",v.text.strip())
                         and ux1-hh*.5 <= (bounds(v)[0]+bounds(v)[2])/2 <= unit_right+hh*.5
                         and abs((bounds(v)[1]+bounds(v)[3]-y1-y2)/2) < hh]
                if len(units) != 1:
                    continue
                unit = units[0].text.strip()
                confidence = min(confidence,units[0].confidence)
            output.append(Item(qty=match[1],uom=unit.upper(),confidence=confidence,
                               source=f"QTY ↓ {match[1]} · UOM ↓ {unit.upper()}"))
    return output
