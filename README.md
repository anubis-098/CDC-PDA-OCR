# ตรวจรับ · PDA Document Check

MVP สำหรับเทียบ Checking Sheet กับ Invoice บน PDA Zebra Android ตาม [start.md](start.md): React + TypeScript + Vite + Tailwind, FastAPI, PaddleOCR CPU, PostgreSQL และ Docker Compose

**สถานะ:** Docker Compose และ frontend build ผ่านแล้ว ชุดทดสอบ backend ผ่าน 25 ข้อ ยังไม่ได้ทดสอบบน PDA จริง ดูผลตรวจ OCR และรายละเอียดล่าสุดใน [docs/verification.md](docs/verification.md)

## เริ่มระบบ

ต้องมี Docker Engine/Desktop พร้อม Compose และอินเทอร์เน็ตเพื่อดาวน์โหลด image, Python/npm packages และโมเดล OCR ครั้งแรก ใช้ Linux containers บน Windows โมเดล CPU อาจใช้เวลาหลายนาทีในการเริ่มครั้งแรก

```powershell
Copy-Item .env.example .env
docker compose up --build
```

เปิด `https://localhost` บนเครื่องเซิร์ฟเวอร์ ค่าเริ่มต้นใช้ใบรับรองจาก Caddy local CA ต้องติดตั้ง CA ให้เบราว์เซอร์เชื่อถือก่อนใช้งานกล้อง ไม่ใช่เพียงข้ามหน้าคำเตือน certificate

สำหรับพัฒนาบนเครื่องนี้ เปิด `http://localhost:8080` ได้โดยตรง (`8080` → พอร์ต `80` ของ web container) และใช้ API ผ่าน `http://localhost:8080/api` เปลี่ยนพอร์ตได้ด้วย `DEV_PORT` ใน `.env` พอร์ตนี้เปิดบน network interface ของเครื่องเพื่อให้ PDA ใน Internal LAN เข้าได้ เช่น `http://10.84.194.51:8080` การเปิดกล้องจาก PDA ผ่าน HTTP อาจถูก browser บล็อกเพราะต้องใช้ secure context; ให้ใช้ HTTPS ผ่าน gateway ตามขั้นตอนด้านล่างเมื่อทดสอบกล้อง

เว็บใน Docker เสิร์ฟไฟล์ที่ build แล้ว หลังแก้โค้ดใช้ `docker compose up -d --build --no-deps web` เพื่ออัปเดตหน้าเว็บ

API docs: `https://localhost/api/docs` · Health: `https://localhost/api/health`

Compose เริ่มฐานข้อมูล → migration → API → เว็บ → HTTPS proxy ฐานข้อมูลและ API ไม่เปิด port ออก host โดยตรง; `/api` ใช้ same origin กับเว็บ

### เปิดจาก PDA ในเครือข่ายทดสอบ

1. ให้ PDA และเซิร์ฟเวอร์อยู่เครือข่ายเดียวกัน กำหนด IP ของเซิร์ฟเวอร์ให้คงที่ เช่น `192.168.1.50` แล้วตั้ง `.env`:

   ```dotenv
   SITE_ADDRESS=192.168.1.50
   TLS_MODE=internal
   ```

2. รัน `docker compose up -d --build` และเปิด firewall เฉพาะเครือข่ายที่อนุญาตบน port 80/443
3. ส่งออก **เฉพาะ public root certificate**:

   ```powershell
   docker compose cp gateway:/data/caddy/pki/authorities/local/root.crt ./pda-local-root.crt
   ```

4. ติดตั้ง root CA นี้บนเครื่องทดสอบ/PDA ผ่านนโยบายองค์กรหรือ Android certificate settings; managed browser/kiosk บางแบบไม่เชื่อถือ user CA ต้องให้ผู้ดูแลติดตั้งผ่าน MDM ตรวจ certificate chain ให้ผ่าน
5. เปิด `https://192.168.1.50` บน PDA กด `ถ่าย Checking Sheet` แล้วอนุญาตกล้องใน browser/site settings หากนโยบายองค์กรปิดกล้อง ให้ใช้ปุ่มเลือกไฟล์
6. ขั้นตอน 1: ถ่าย Checksheet → `ใช้เอกสารนี้ → ไปถ่าย Invoice` → ขั้นตอน 2: ถ่าย Invoice → `ใช้เอกสารนี้ → อ่านและสรุปผล` ระบบ OCR เอกสารทั้งคู่แล้วเปิดขั้นตอน 3 ซึ่งแสดงภาพพร้อมข้อความที่อ่านได้
7. แตะภาพเพื่อซูม กดปุ่ม X มุมขวาบนเพื่อปิด แล้วเลือก `ดูสรุปผลเทียบเอกสาร` เพื่อไปขั้นตอน 4 หน้าสรุปแสดงผล PO และ QTY; เปิด `ดูข้อมูลที่อ่านได้ / แก้ไขข้อมูล` เมื่อต้องการแก้ค่า ระบบบันทึกและคำนวณผลใหม่อัตโนมัติ
8. เมื่อติดตั้ง PWA ให้ใช้เมนู browser “ติดตั้งแอป” / “เพิ่มในหน้าจอหลัก” ตามความสามารถของ browser

`http://<IP ของเซิร์ฟเวอร์>` ไม่ใช่ secure context แบบ localhost ของเครื่อง PDA จึงใช้กล้องไม่ได้

### Staging / server ที่มีโดเมน

ตั้ง `SITE_ADDRESS=pda.example.com` เป็นโดเมนจริงที่ DNS ชี้มายังเซิร์ฟเวอร์ และตั้ง `TLS_MODE=admin@your-domain.com` เป็นอีเมลผู้ดูแลจริง เพื่อให้คำสั่ง `tls` ของ Caddy ใช้ ACME แทน internal CA โดเมนต้องตรวจสอบได้จาก certificate issuer และ port 80/443 ต้องเข้าถึงได้ตามวิธี challenge ที่ใช้

MVP นี้ยังไม่มี login/สิทธิ์รายผู้ใช้ ทุกคนที่เข้าถึงเว็บได้จะเห็นและแก้ประวัติได้ ใช้ในเครือข่ายที่ควบคุมหรือหลัง authentication gateway ขององค์กร ก่อนเปิดให้บุคคลภายนอกต้องเพิ่ม access control

## ความสามารถ

- หน้าไทยแบบ mobile-first ปุ่มใหญ่ มีสถานะว่าง/ส่งภาพ/อ่านเอกสาร/ผิดพลาด/ผลลัพธ์
- กล้องหลังผ่าน adapter `getUserMedia()` เปิดหลังแตะปุ่ม มี live preview ถ่ายใหม่ ยืนยันภาพ และปิด camera tracks เมื่อถ่าย/ออกจากหน้า/สลับแอป
- เลือก JPG/JPEG/PNG/PDF ได้ ตรวจไฟล์จากเนื้อหาจริง ไม่เชื่อ MIME/นามสกุลเพียงอย่างเดียว
- จำกัด 10 MB ต่อไฟล์, ภาพ 25 ล้านพิกเซล, PDF 1–5 หน้า ไม่รับ PDF เข้ารหัสหรือภาพเคลื่อนไหว; proxy จำกัด request รวม 22 MB
- หมุนภาพตาม EXIF และลดด้านยาวสูงสุด 2,400 px; PDF render เป็น RGB ก่อน OCR
- PaddleOCR แบบ CPU ใช้ PP-OCRv5 ภาษาไทย (`OCR_LANG=th`; explicitly selects the Thai PP-OCRv5 mobile recognizer, which also recognizes English and digits in one pass) พร้อม confidence, page และ polygon; ใช้ mobile detector จำกัดด้านตรวจจับ 1,280 px และปิดตัวจำแนกทิศทาง/แก้ภาพเอียงเพื่อลดเวลาประมวลผลสำหรับเอกสารที่ถ่ายตรง
- ถอดรหัสบาร์โค้ดบน Checking Sheet โดยตรงแล้วใช้เป็นเลขอ้างอิง; หากถอดรหัสไม่ได้จะใช้ `ASN No.` / `SN No.` จาก OCR เป็นทางสำรอง และเลือกจำนวนจาก `Quantity Plan (CS)`
- ตัวอ่านบาร์โค้ดรองรับ Code 39 และตรวจหารูปแบบบาร์โค้ดที่อ่านได้ในภาพโดยอัตโนมัติ
- หาก OCR รวม `Plan (CS)`, `Rec (CS)`, `Plan (MU)` และ `Rec (MU)` เป็นหัวข้อเดียว จะ OCR ซ้ำเฉพาะช่อง `Quantity Plan (CS)` แบบขยายภาพ เพื่อไม่เอาจำนวนจากคอลัมน์ MU มาแทน CS
- PO เก็บเป็นข้อความ รักษาเลขศูนย์นำหน้า; normalization ตัดช่องว่าง/ขีดและปรับตัวพิมพ์
- จำนวนใช้ Python Decimal รองรับ `1`, `1.00`, `1,000.50`; ไม่รับ NaN, infinity, จำนวนลบหรือ comma ที่แบ่งหลักไม่ถูกต้อง
- เปรียบเทียบหน่วยเดียวกันเท่านั้น ไม่แปลง CS ↔ MU และไม่รวมจำนวนหลายรายการเพื่อเดาว่าตรง
- หลายรายการต้องมีรหัสที่ไม่ซ้ำและจับคู่ได้ครบทั้งสองฝั่ง; รหัสต่างกันหรือกำกวมให้ตรวจทาน
- เก็บ OCR ดิบ หลักฐาน ค่าที่แก้ ผลลัพธ์และ timestamps ใน PostgreSQL; เก็บการแก้แต่ละครั้งใน `comparison_revisions`
- PATCH ใช้ revision และ row lock ป้องกันการแก้ทับข้อมูลเก่า; ต้องเปิดประวัติใหม่หากเกิด conflict
- ประวัติแบ่งหน้าและเปิดรายละเอียดได้ การกดอ่านสำเร็จจะบันทึกผลเบื้องต้น; การแก้ไขจะบันทึกและเทียบใหม่อัตโนมัติเป็น revision ใหม่
- ภาพที่ยังอยู่ใน browser session ไม่หายเมื่อ network error จึงลองส่งใหม่ได้; reload หน้าแล้วต้องเลือกใหม่
- PWA manifest + icons + service worker ขั้นต่ำ ไม่ cache เอกสารหรือผล API และไม่รองรับ OCR ออฟไลน์

## ข้อจำกัด OCR ที่ต้องตรวจต่อ

Rule-based extraction อ่าน label/value ชัดเจนได้ แต่ไม่ใช่ระบบเข้าใจตารางทุกแบบ เมื่อใช้ตำแหน่งคอลัมน์เป็นหลักจะเสนอค่าและแสดง `ต้องตรวจทาน` ข้อความเอียง เงา เลขเล็ก คอลัมน์หัวตารางหลายบรรทัด และตารางที่มี subtotal อาจทำให้เสนอค่าขาดหรือเกินได้ ผู้ใช้แก้/เพิ่ม/ลบแถวได้ และระบบจะคำนวณใหม่ทันทีหลังแก้

ตัวอย่าง `sample/checking sheet.jpg` อ่าน `SN No. 1132536` เป็นเลขอ้างอิง และอ่านเฉพาะช่อง `Quantity Plan (CS)` ได้ `1 CS` โดยไม่หยิบ `5` จาก `Plan (MU)` มาใช้; ตัวอย่าง `sample/invoice.jpg` ยังต้องตรวจจำนวน Invoice ตามข้อจำกัด extraction ปัจจุบัน ภาพจริงไม่ถูกฝังใน Docker image และถูก ignore จาก Git

โมเดลดาวน์โหลดเมื่อใช้ OCR ครั้งแรก หากดาวน์โหลดไม่ได้ API ตอบ 503; `health` ตรวจ API/DB เท่านั้น ไม่ยืนยันว่าโมเดลโหลดสำเร็จ ปัจจุบันอ่านครั้งละหนึ่งคู่ต่อ API worker หากเครื่องกำลังอ่านคู่อื่นจะตอบ 429 ไม่จัดคิวหรือมี background broker อย่าเพิ่ม workers โดยไม่ประเมิน RAM/CPU

ค่าความเชื่อมั่นต่ำกว่า `MIN_CONFIDENCE=0.85` จะแสดง `ต้องตรวจทาน` โดยอัตโนมัติ คะแนน OCR ไม่รับประกันความถูกต้อง การแก้ข้อมูลจะถูกเทียบใหม่ทันที แต่ระบบยังตรวจรหัส จำนวน และหน่วยตามกฎเดิม และไม่เปลี่ยนสถานะเป็น match หากยังมีคำเตือนหรือค่าความเชื่อมั่น OCR ต่ำ

## โครงสร้าง

```text
backend/
  app/
    main.py          API, validation, history, revision conflict
    schemas.py       request/response contract + Decimal parsing
    comparison.py    กฎตัดสิน PO / QTY / UOM
    extraction.py    label rules + spatial table suggestions
    ocr.py           PaddleOCR adapter
    files.py         file validation, EXIF, PDF rendering
    db.py            SQLAlchemy models
    cleanup.py       ลบไฟล์ที่ตกค้างจาก process crash
  migrations/        Alembic schema migration
  tests/             unit + API integration tests (mock OCR)
  scripts/           สร้างเอกสารจำลอง
frontend/
  src/components/    CaptureCard และ Results/editor
  src/camera.ts      browser camera adapter
  src/api.ts         API client + upload progress
  src/types.ts       frontend contract
  public/            PWA manifest, service worker, icons
infra/Caddyfile       TLS/reverse proxy
fixtures/            ข้อความจำลอง ไม่ใช่เอกสารลูกค้า
scripts/             สร้างไอคอนและตรวจโครงสร้างแบบไม่ใช้ dependencies
docs/                สถานะการทดสอบและรายการตรวจบน PDA
compose.yaml
.env.example
```

`documents.original/current` เก็บรายการสินค้าใน JSON ซึ่งเป็นโครงสร้างเทียบเท่า extracted_items และรักษา snapshot ขณะเปรียบเทียบได้ครบ ไม่เก็บ binary ใน PostgreSQL

## API

| Method | Path | หน้าที่ |
| --- | --- | --- |
| GET | `/api/health` | ตรวจ API และ DB |
| POST | `/api/comparisons` | multipart `checking` + `invoice`, OCR และบันทึกผลเบื้องต้น |
| GET | `/api/comparisons?page=1&page_size=10` | ประวัติ (page_size สูงสุด 50) |
| GET | `/api/comparisons/{uuid}` | หลักฐาน ค่าดิบ/ค่าปัจจุบัน ผลลัพธ์ |
| PATCH | `/api/comparisons/{uuid}` | บันทึกการแก้ทั้งสองเอกสารและคำนวณใหม่อัตโนมัติ |

PATCH body ตัวอย่าง:

```json
{
  "revision": 1,
  "checking": { "po": "1132536", "items": [{ "code": "", "qty": "1", "uom": "CS" }] },
  "invoice": { "po": "1132536", "items": [{ "code": "", "qty": "1.00", "uom": "CS" }] }
}
```

ระบบบันทึกการแก้ไขเป็น revision ใหม่ โดยไม่ยกระดับ confidence ของ OCR ที่ไม่ได้แก้; ค่าแก้ไขระบุแหล่งที่มาเป็นผู้ใช้ ระบบไม่ให้ client ส่ง confidence มาเพิ่มคะแนน OCR และ API ปฏิเสธ fields ที่ไม่รู้จักด้วย Pydantic

## ไฟล์ชั่วคราวและข้อมูลทดสอบ

อัปโหลดอยู่ใน named volume `uploads` ในโฟลเดอร์สุ่ม ใช้ชื่อจากผู้ใช้เป็น metadata เท่านั้น ลบไฟล์หลังจบคำขอทั้งกรณีสำเร็จและ error จึงไม่สามารถเปิดรูปเก่าย้อนหลังจากเซิร์ฟเวอร์ได้ (ยังมี OCR text, polygon, ค่าดิบและผลลัพธ์)

หาก process crash อาจมีไฟล์ตกค้าง ตั้ง scheduler บน host ให้เรียกวันละครั้ง:

```sh
docker compose exec -T api python -m app.cleanup
```

ลบเฉพาะ directory `request-*` ที่อยู่ใต้ upload root และเก่ากว่า 24 ชั่วโมง ไม่ตาม symlink; volume โมเดล OCR เก็บไว้ใช้ครั้งถัดไป

ล้าง **เฉพาะประวัติทดสอบทั้งหมด** (คำสั่งนี้ลบข้อมูลถาวร ไม่ได้รันให้โดยอัตโนมัติ):

```sh
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "TRUNCATE comparison_revisions, documents, comparisons;"'
```

`docker compose down` หยุดระบบโดยเก็บ volumes ไว้ ไม่ต้องลบ CA หรือโมเดลทุกครั้งที่รีสตาร์ต

## พัฒนาและทดสอบ

Backend tests ใช้ SQLite ชั่วคราวและ mock OCR ไม่ดาวน์โหลดโมเดล; ต้องทดสอบ PostgreSQL/migration และ PaddleOCR จริงผ่าน Compose เพิ่มก่อนรับงาน

```sh
cd backend
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
```

หากต้องรัน API พร้อม OCR นอก Docker ให้ติดตั้ง `requirements.txt` แทน ตั้ง `DATABASE_URL`, `UPLOAD_DIR` ให้เหมาะกับเครื่อง แล้วรัน `alembic upgrade head` และ `uvicorn app.main:app --reload` Frontend dev proxy ส่ง `/api` ไป `http://localhost:8000`

```sh
cd frontend
npm install
npm run build
npm run dev
```

จาก root ของโปรเจกต์:

```sh
node scripts/generate-icons.mjs
node scripts/check-structure.mjs
docker compose config --quiet
```

สร้าง PDF จำลองสำหรับทดสอบ upload (ต้องติดตั้ง Python dependencies แล้ว):

```sh
python backend/scripts/generate_samples.py
```

ไฟล์จะอยู่ใน `fixtures/generated/` คู่จำลองไม่มีข้อมูลจริง UI ไม่รับ `.txt`; ข้อความ fixture ใช้เป็นข้อมูลอ้างอิงสำหรับกฎ extraction เท่านั้น

### Dependencies

ใช้ Node 24 / Python 3.11 เป็น runtime baseline มี `frontend/package-lock.json` แล้ว และ Docker/CI ใช้ `npm ci` ฝั่ง Python มี `backend/requirements.lock.txt` เป็น snapshot ของ dependencies จาก Linux image ที่ทดสอบ เพื่อใช้ติดตั้งรุ่นเดิมด้วย `pip install -r requirements.lock.txt` ส่วน Dockerfile ยัง resolve ตาม ranges ใน `requirements.txt` และเก็บผล `pip freeze` ใน `/app/requirements.resolved.txt` ของแต่ละ image

OCR ใช้ `PP-OCRv5_mobile_det` สำหรับ CPU และจำกัดด้านยาวของภาพตรวจจับที่ 1,280 px (ภาพสำหรับอ่านข้อความยังเตรียมที่สูงสุด 2,400 px) ปิด MKL-DNN เพราะพบข้อผิดพลาด `ConvertPirAttribute2RuntimeAttribute` ใน runtime ที่ทดสอบ และใช้ CPU 4 threads

ทดสอบ OCR จริงด้วยเอกสารจำลอง (สร้างประวัติทดสอบหนึ่งรายการ):

```sh
docker compose exec -T api python scripts/smoke.py
```

เอกสารอ้างอิงสำหรับ adapter/configuration:
- [PaddleOCR official pipeline และโมเดลภาษาไทย](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/OCR.en.md)
- [Vite getting started](https://vite.dev/guide/)
- [Tailwind Vite plugin](https://tailwindcss.com/docs/installation/using-vite)

## การทดสอบอุปกรณ์

ยังไม่มีการระบุรุ่น Zebra, Android version หรือ browser/kiosk policy และ **ยังไม่ได้ทดสอบอุปกรณ์จริง** ใช้ [docs/pda-checklist.md](docs/pda-checklist.md) บันทึกผลก่อนนำไปใช้หน้างาน
