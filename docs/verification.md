# ผลตรวจในสภาพแวดล้อมสร้างงาน

## ปรับ extraction ตามภาพ Checksheet จริง (2026-10-27)

- OCR `sample/checking sheet.jpg` ใน container โดยไม่สร้างประวัติฐานข้อมูล ได้เลขอ้างอิง `1132536` จาก `SN No.` ที่ OCR อ่าน (หัว ASN ถูกขอบภาพบัง)
- OCR ซ้ำเฉพาะช่องที่อยู่ใต้ Quantity Plan (CS) แบบขยาย ได้ `1 CS` ความเชื่อมั่น 94.8%; ป้องกันการใช้ `5` ซ้ำจาก Plan (MU) ที่ OCR เดิมรวมเป็นหัวข้อเดียว
- ZXing-C++ รองรับ Code 39 และตรวจหารูปแบบในภาพโดยอัตโนมัติ; ภาพตัวอย่างนี้ตัวถอดรหัสจัดเป็น Code 128 (`1132536`) ขณะที่การบังคับอ่าน Code 39 อย่างเดียวไม่พบค่า จึงเปิดการตรวจหลายรูปแบบและใช้ OCR `SN No.` เป็นทางสำรอง
- ยังต้องปรับการดึงจำนวนจาก Invoice ใน `sample/invoice.jpg` แยกต่างหาก

## ขั้นตอน OCR และขยายภาพ (2026-10-27)

- หลังเลือก Invoice ระบบ OCR ทั้งคู่ แล้วเปิดขั้นตอนตรวจ OCR พร้อมภาพและข้อความทับตำแหน่ง ก่อนผู้ใช้ไปหน้าสรุปแยกต่างหาก
- แตะภาพเปิดภาพขยายเต็มจอ มีปุ่ม X มุมขวาบนและกด Escape เพื่อปิด
- `npm run build` และ Docker web rebuild ผ่านหลังเพิ่ม OCR viewer และ zoom
- ก่อนการเปลี่ยนแปลง OCR viewer มีการทดสอบ flow ด้วย headless Chrome + API จำลอง: ลำดับขั้น, ย้อนกลับแล้วรูปยังอยู่, ส่ง OCR ครั้งเดียว, auto-save, เริ่มรายการใหม่, retry error/offline, ประวัติ และ viewport 360×640/1280×800 ภาพอยู่ที่ `wizard-checksheet.png` และ `wizard-summary.png`
- ภาพบน viewer ใช้ไฟล์ที่ค้างใน browser สำหรับหน้าแรก; PDF ใช้ OCR evidence แบบข้อความแทน และประวัติที่ไม่มีภาพต้นฉบับไม่แสดง overlay

วันที่ 2026-10-24

## สถานะล่าสุดหลังเปิด permission

- Agent เรียก Docker CLI และเข้าถึง npm registry ได้แล้ว ข้อจำกัดสิทธิ์ที่บันทึกด้านล่างเป็นประวัติก่อนแก้ไข
- `docker compose config --quiet`, `docker compose up -d --build` และ `docker compose up -d --wait` ผ่าน; api/db healthy และ web/gateway ทำงาน
- `alembic current` ใน API container: `0001 (head)` บน PostgreSQL
- `npm install` และ `npm run build` ผ่านบน Windows (TypeScript + Vite 7.3.7); Docker frontend build ผ่านด้วย `npm ci`
- ชุดทดสอบ backend บน Python 3.11 ใน container รุ่นล่าสุด: **25 passed in 2.62s** (unit tests และ API tests ที่ mock OCR)
- ทดสอบ **PaddleOCR จริง** ผ่าน `docker compose exec -T api python scripts/smoke.py`: PDF จำลองสองฉบับได้ PO `1132536` ทั้งคู่, QTY `1 CS` เท่ากับ `1.00 CS`, สถานะ `match`; GET detail ที่บันทึกลง PostgreSQL ผ่าน
- แก้ OCR runtime: ปิด MKL-DNN หลังพบ `ConvertPirAttribute2RuntimeAttribute`; โมเดล server ทำให้ process ถูก kill ระหว่าง inference จึงใช้ `PP-OCRv5_mobile_det` และจำกัด detection ด้านยาว 1,280 px แทน หลังแก้ smoke test ผ่าน
- Runtime ที่ใช้: PaddleOCR 3.7.0, PaddlePaddle 3.3.1, PaddleX 3.7.2; snapshot Python dependencies อยู่ใน `backend/requirements.lock.txt`
- HTTPS health ตอบ `{"status":"ok","ocr":"lazy-loaded"}` เมื่อระบุ Caddy CA ด้วย `curl --cacert pda-local-root.crt --ssl-revoke-best-effort` (Windows Schannel ไม่พบ revocation status ของ local CA หากไม่ใช้ best-effort)
- ตรวจภาพหน้าเว็บจริงผ่าน headless Chrome ที่ viewport 390×844 และ 1366×900: `docs/ui-mobile.png` และ `docs/ui-desktop.png`; การจับภาพใช้ ignore-https-errors เฉพาะ browser ทดสอบ จึงไม่ใช่การยืนยันว่า Windows/browser/PDA ติดตั้ง CA แล้ว
- ส่งออก public Caddy CA ไป `pda-local-root.crt` แล้ว แต่ไม่ได้ติดตั้งเข้า trust store ของ Windows/PDA
- ทดลอง upload ภาพจริงใน `sample/` ผ่าน HTTPS แล้ว: PO ทั้งคู่ `1132536` ตรงกัน, Checking Sheet เสนอ `1 CS`, Invoice ยังดึง QTY ไม่ได้ ผลรวม `review` ตามกฎ ไม่รายงานผ่านผิด ๆ; ยังต้องปรับ extraction สำหรับตาราง Invoice หรือเพิ่มรายการด้วยมือ
- มีประวัติใหม่จากการทดสอบสองรายการ (PDF จำลองและภาพตัวอย่าง) ไม่ได้ลบประวัติเดิมของผู้ใช้
- ยังไม่ได้ทดสอบกล้องจริง, Android/PDA, kiosk policy หรือ PWA installation; ยังไม่ได้รัน CI บน GitHub

## ประวัติการตรวจช่วงที่สิทธิ์ยังจำกัด

## CI และฟอนต์หน้าเว็บ

- `frontend/index.html` โหลด Sarabun 400/500/600/700 จาก Google Fonts ผ่าน `fonts.googleapis.com`/`fonts.gstatic.com`; เบราว์เซอร์ทดสอบรายงาน Sarabun loaded 6 faces
- สี CJ Logistics จากหน้า Brand Story ทางการ: blue `#0080c6`, red `#e42f44`, yellow `#ec8922`, silver `#cdcdce`; ใช้ blue เข้มกว่า `#006ba6` สำหรับปุ่มและลิงก์เพื่อคงความอ่านง่าย และเก็บสีเขียวไว้แสดงสถานะผ่าน
- ดาวน์โหลดโลโก้ CJ Logistics ต้นฉบับจาก asset URL ทางการ แสดงตามสัดส่วนเดิม ไม่วาดโลโก้ขึ้นใหม่
- `npm run build` หลังปรับแบรนด์ ผ่านด้วย TypeScript และ Vite 7.3.7
- `docker compose up -d --build --no-deps web` สร้าง/เปิดหน้าเว็บ CI รุ่นใหม่ผ่าน
- Headless Chrome ตรวจหน้ามือถือ 390×844 และ desktop 1366×900: Sarabun โหลดครบ, โลโก้กว้าง 124 px, ไม่มี horizontal overflow ที่มือถือ, ไม่มี page errors; ภาพที่ตรวจบันทึกใน `docs/ui-mobile.png` / `docs/ui-desktop.png`

## ตรวจแล้ว

- อ่าน `start.md` แบบ UTF-8 และตรวจ repository เดิม: มีเพียงไฟล์โจทย์และภาพใน `sample/`
- ตรวจภาพตัวอย่างเพื่อดูโครงสร้างตาราง ไม่ได้รัน OCR หรือคัดลอกภาพเข้าแอป
- พบ Node.js `v24.22.1`, npm `11.19.1`
- `node scripts/generate-icons.mjs` สร้าง PNG สำหรับ PWA ขนาด 192/512
- `node --check frontend/public/sw.js` ผ่าน
- `node --check frontend/src/api.ts` ผ่าน (syntax เท่านั้น ไม่ใช่ TypeScript typecheck)
- `node --check frontend/src/camera.ts` ผ่าน (syntax เท่านั้น)
- `node --check frontend/src/types.ts` ผ่าน (syntax เท่านั้น)
- `node --check scripts/generate-icons.mjs` และ `node --check scripts/check-structure.mjs` ผ่าน
- `node scripts/check-structure.mjs` ผ่าน: JSON, local TypeScript imports, PWA PNG dimensions และไฟล์ configuration ที่จำเป็น
- ตรวจแล้วว่าโฟลเดอร์ยังไม่ใช่ Git repository (`git status` ตอบ not a git repository) ไม่ได้สร้าง commit หรือแก้ `start.md`/ภาพต้นฉบับ

## ยังตรวจไม่สำเร็จ / ยังไม่ได้รัน

- `npm view` ของ dependencies ล้มเหลวด้วย `EACCES` เมื่อเชื่อมต่อ `registry.npmjs.org`; npm cache ว่าง จึงติดตั้งหรือสร้าง lockfile ไม่ได้
- การอ่าน package metadata จาก PyPI ผ่าน shell ไม่สำเร็จ
- ไม่พบ `python`, `py`, `docker` ใน PATH; การค้นในพื้นที่ที่อ่านได้ก็ไม่พบ Python/Docker executable
- รัน `npm run build` แล้ว **ไม่ผ่าน** ที่ไม่พบคำสั่ง `tsc` เพราะยังไม่มี dependencies; ยังไม่ได้ทำ TypeScript typecheck หรือ Vite build
- ยังไม่ได้รัน `pytest`, `alembic upgrade head`, `docker compose up --build` หรือ OCR จริง
- ยังไม่ได้ทดสอบ UI ใน browser, กล้อง, HTTPS trust, PWA installation หรือ PDA Zebra จริง
- CI workflow เตรียมไว้แล้ว แต่ยังไม่เคยรันใน repository นี้

ผล structural check ไม่ใช่หลักฐานว่า runtime หรือ acceptance criteria ทั้งหมดผ่าน ต้องรันขั้นตอนใน README บนเครื่องที่ติดตั้ง dependencies และ Docker ได้ก่อนรับงาน

## ตรวจซ้ำหลังติดตั้ง Python และเปิด Docker

- พบ process ของ Docker Desktop และ `com.docker.backend` ทำงานอยู่ โดย path อยู่ใต้ `C:\Users\autthavutna\AppData\Local\Programs\DockerDesktop`
- พบรายการติดตั้ง Python ใน Windows uninstall registry แล้ว
- แต่ `Get-Command`, `python --version` และ `docker version` ใน terminal ของเซสชันนี้ยังหา executable ไม่พบ และการตรวจโฟลเดอร์ Programs ของผู้ใช้ได้รับ `Access is denied`
- ทดลองเรียก executable จาก path ที่คาดไว้โดยตรงแล้ว ยังเรียกไม่ได้ จึงยังยืนยัน Docker Engine readiness หรือเวอร์ชัน Python ที่รันจริงไม่ได้
- ทดลอง `npm install --cache .npm-cache --fetch-retries=0 --fetch-timeout=15000 --no-audit --no-fund` ใน frontend แล้ว ยังล้มเหลวด้วย `EACCES` ขณะเชื่อมต่อ npm registry แม้กำหนด cache ภายใน workspace
- ยังไม่ได้รัน tests/build เพิ่มสำเร็จ จำเป็นต้องเปิดเซสชัน terminal ใหม่ที่มองเห็น executable และมีสิทธิ์เข้าถึง package registry ก่อนดำเนินการต่อ

## Docker Engine ยืนยันจาก PowerShell ของผู้ใช้

ผู้ใช้ส่งผล `docker version` ที่เรียกสำเร็จจาก PowerShell:

- CLI: `C:\Users\autthavutna\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`
- Client และ Server Engine: 29.9.2, API 1.56
- Docker Desktop: 4.96.3 (244472)
- Context: `desktop-linux`; Server OS/Arch: `linux/amd64`

ผลนี้ยืนยันว่า Engine พร้อมตอบคำสั่งจาก terminal ของผู้ใช้แล้ว ไม่ใช่ผล build ของโปรเจกต์ Terminal ของ agent ยังมีข้อจำกัดการเข้าถึง executable จึงต้องเริ่ม Compose จาก PowerShell ของผู้ใช้หรือจากเซสชันที่ได้รับสิทธิ์เข้าถึง Docker
