import { useEffect, useMemo, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { request } from '../api'
import { statusLabels, titles, type Comparison, type Extracted, type Kind, type Status } from '../types'

export const Badge = ({ status }: { status: Status }) => <span className={`badge ${status}`}>{statusLabels[status]}</span>

function OCRPreview({ file, document }: { file?: File; document: Comparison['documents'][number] }) {
  const image = useMemo(() => file && !/\.pdf$/i.test(file.name) ? URL.createObjectURL(file) : '', [file])
  const [size, setSize] = useState({ width: 0, height: 0 })
  const [zoomed, setZoomed] = useState(false)
  const zoomButton = useRef<HTMLButtonElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  useEffect(() => { setSize({ width: 0, height: 0 }); return () => { if (image) URL.revokeObjectURL(image) } }, [image])
  useEffect(() => {
    if (!zoomed) return
    const previousOverflow = window.document.body.style.overflow
    window.document.body.style.overflow = 'hidden'
    closeButton.current?.focus()
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setZoomed(false) }
    window.addEventListener('keydown', onKey)
    return () => { window.document.body.style.overflow = previousOverflow; window.removeEventListener('keydown', onKey); zoomButton.current?.focus() }
  }, [zoomed])
  const tokens = (values: string[]) => values.map(value => value.trim().toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu, '')).filter(Boolean)
  const poValues = tokens([document.original.po, document.current.po])
  const rect = (box: number[][]) => ({ left: Math.min(...box.map(p => p[0])), right: Math.max(...box.map(p => p[0])), top: Math.min(...box.map(p => p[1])), bottom: Math.max(...box.map(p => p[1])) })
  const classify = (line: Comparison['documents'][number]['evidence'][number]): 'green' | 'red' => {
    const text = line.text
    if (/discount|net\s*amount|vat|tax\s*invoice|total\s*amount|price/i.test(text)) return 'red'
    if (/\b(?:p\.?\s*o\.?|purchase\s*order|a?sn|srn)\s*(?:no|date|:)|ใบสั่งซื้อ/i.test(text)) return 'green'
    const token = tokens([text])[0]
    if (token && poValues.includes(token)) return 'green'
    const headerPattern = document.kind === 'checking' ? /^(?:Quantity\s*)?Plan\s*\(\s*(?:CS|MU)\s*\)$|^Grand\s*Total\s*: ?$/i : /^(?:QTY|UOM)$/i
    if (headerPattern.test(text.trim())) return 'green'
    if (!line.box.length) return 'red'
    const cell = rect(line.box)
    const cx = (cell.left + cell.right) / 2
    const cy = (cell.top + cell.bottom) / 2
    for (const reference of document.evidence.filter(v => v.page === line.page && v.box.length && /(?:PO|SRN)\s*Date/i.test(v.text))) {
      const r = rect(reference.box)
      if (/^\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}$/.test(text.trim()) && cell.left >= r.right && Math.abs(cy - (r.top + r.bottom) / 2) < r.bottom - r.top) return 'green'
    }
    if (document.kind === 'checking') {
      for (const fused of document.evidence.filter(v => v.page === line.page && v.box.length && (v.text.match(/(?:Plan|Rec)\s*\(/gi)?.length || 0) > 1)) {
        const f = rect(fused.box), height = f.bottom - f.top
        const labels = [...fused.text.matchAll(/(Plan|Rec)\s*\(\s*(CS|MU)\s*\)/gi)]
        const columns = document.evidence.filter(v => v.page === line.page && v.box.length && /^Quantity$/i.test(v.text.trim())).map(v => rect(v.box)).filter(r => r.left >= f.left - height && r.right <= f.right + height && Math.abs(r.bottom - f.top) < height * 2).sort((a, b) => a.left - b.left)
        if (columns.length === labels.length && /^(?:Quantity|\d[\d,.]*)$/i.test(text.trim())) {
          for (let i = 0; i < columns.length; i++) {
            const c = columns[i]
            if (labels[i][1].toLowerCase() === 'plan' && cx >= c.left && cx <= c.right + height * .25 && cell.top >= c.top && cell.bottom <= f.bottom + height * 1.5) return 'green'
          }
        }
      }
    }
    const anchors = document.evidence.filter(v => v.page === line.page && v.box.length && headerPattern.test(v.text.trim()))
    for (const anchor of anchors) {
      const h = rect(anchor.box), height = Math.max(h.bottom - h.top, 1)
      if (/^Grand/i.test(anchor.text) && /^\d+(?:\.\d+)?$/.test(text.trim()) && cell.left > h.right && Math.abs(cy - (h.top + h.bottom) / 2) < height) return 'green'
      if (/^(?:\d[\d,.]*(?:\s+[A-Z]{1,6})?|CS|MU|Quantity)$/i.test(text.trim()) && cx >= h.left - height * .5 && cell.left <= h.right + height * .5 && cell.top > h.top - height * 2 && cell.bottom < h.bottom + height * 5) return 'green'
    }
    return 'red'
  }
  const marks = document.evidence.filter(line => line.page === 1 && line.box.length >= 4 && line.box.every(point => point.length >= 2 && point.every(Number.isFinite)))
  const pdf = file && /\.pdf$/i.test(file.name)
  const overlay = image && <>
    <img src={image} alt={`ภาพ ${titles[document.kind]} พร้อมตำแหน่งข้อความ OCR`} onLoad={event => setSize({ width: event.currentTarget.naturalWidth, height: event.currentTarget.naturalHeight })} />
    {size.width > 0 && <div className="ocr-label-layer">{marks.map((line, index) => {
        const xs = line.box.map(point => point[0]); const ys = line.box.map(point => point[1])
        const left = Math.max(0, Math.min(...xs)); const top = Math.max(0, Math.min(...ys)); const right = Math.min(size.width, Math.max(...xs)); const bottom = Math.min(size.height, Math.max(...ys))
        if (right <= left || bottom <= top) return null
        const kind = classify(line)
        return <span key={`${line.page}-${index}`} className={`ocr-label ${kind}`} title={`${line.text} · ${Math.round(line.confidence * 100)}%`} style={{ left: `${left / size.width * 100}%`, top: `${top / size.height * 100}%`, width: `${(right - left) / size.width * 100}%`, height: `${(bottom - top) / size.height * 100}%` }}>{line.text}</span>
      })}</div>}
  </>
  return <section className="ocr-preview card"><h3 className="font-bold">{titles[document.kind]}</h3>
    <div className="scan-found"><span>REFERENCE</span><strong>{document.current.po || 'ไม่พบข้อมูล'}</strong><span>QUANTITY</span><strong>{document.current.items.map(item => item.qty + ' ' + item.uom).join(' · ') || 'ยังไม่พบจำนวน'}</strong><small>{document.evidence.length} ข้อความที่อ่านได้</small></div>
    <details className="scan-evidence"><summary>ดูข้อความที่สแกนพบทั้งหมด</summary><pre>{document.ocr_text || 'ไม่พบข้อความ'}</pre></details>
    <div className="ocr-legend" aria-label="คำอธิบายสี"><span className="green">PO / QTY</span><span className="red">ข้อความอื่น</span></div>
    {image && <button ref={zoomButton} type="button" className="ocr-zoom-trigger ocr-image-wrap" aria-label={`ซูมภาพ ${titles[document.kind]}`} onClick={() => setZoomed(true)}>{overlay}</button>}
    {!image && <p className="muted text-sm mt-2">{pdf ? 'ไฟล์ PDF แสดงข้อความ OCR แยกตามหน้าได้ในข้อมูลหลักฐานด้านล่าง' : 'ภาพต้นฉบับไม่มีในหน้านี้ เปิดข้อความ OCR ได้จากข้อมูลหลักฐานด้านล่าง'}</p>}
    {image && !marks.length && <p className="muted text-sm mt-2">ไม่พบตำแหน่งข้อความ OCR บนหน้าแรก</p>}
    {image && document.evidence.some(line => line.page > 1) && <p className="muted text-xs mt-2">แสดงเฉพาะหน้าแรก · หน้าอื่นดูได้ในหลักฐาน OCR</p>}
    {zoomed && <div className="ocr-zoom-backdrop" role="dialog" aria-modal="true" aria-label={`ภาพ OCR ${titles[document.kind]}`} onMouseDown={event => { if (event.target === event.currentTarget) setZoomed(false) }}><button ref={closeButton} type="button" className="ocr-zoom-close" aria-label="ปิดภาพขยาย" title="ปิด" onClick={() => setZoomed(false)}><X size={24} aria-hidden="true" /></button><div className="ocr-zoom-content"><div className="ocr-zoom-image ocr-image-wrap">{overlay}</div></div></div>}
  </section>
}

export function OCRReview({ value, files }: { value: Comparison; files: Partial<Record<Kind, File>> }) {
  return <section className="space-y-4" aria-label="ตรวจข้อความที่อ่านได้"><p className="muted text-sm">แตะภาพเพื่อซูม · PO / QTY สีเขียว · ข้อความอื่นสีแดงเข้ม</p>{value.documents.map(document => <OCRPreview key={`${document.kind}-${value.id}`} document={document} file={files[document.kind]} />)}</section>
}

export function Results({ value, onSaved, onPendingChange, editorOpen, onEditorToggle }: { value: Comparison; onSaved: (value: Comparison) => void; onPendingChange?: (pending: boolean) => void; editorOpen?: boolean; onEditorToggle?: (open: boolean) => void }) {
  const [drafts, setDrafts] = useState<Record<Kind, Extracted>>(() => Object.fromEntries(value.documents.map(d => [d.kind, structuredClone(d.current)])) as Record<Kind, Extracted>)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const paused = useRef(false)
  const result = value.result
  useEffect(() => { onPendingChange?.(dirty); return () => onPendingChange?.(false) }, [dirty, onPendingChange])
  function change(kind: Kind, transform: (data: Extracted) => Extracted) {
    paused.current = false
    setDrafts(previous => ({ ...previous, [kind]: transform(previous[kind]) })); setDirty(true); setError('')
  }
  useEffect(() => {
    if (!dirty || paused.current) return
    const timer = window.setTimeout(() => { void save() }, 650)
    return () => window.clearTimeout(timer)
    // A draft change restarts the short debounce; saving is guarded in save().
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drafts, dirty, retry])

  async function save() {
    if (saving || paused.current) return
    setSaving(true); setError('')
    const edit = (kind: Kind) => ({ po: drafts[kind].po, items: drafts[kind].items.map(({ code, qty, uom }) => ({ code, qty, uom })) })
    try {
      const saved = await request<Comparison>(`/comparisons/${value.id}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ revision: value.revision, checking: edit('checking'), invoice: edit('invoice') }) })
      onSaved(saved)
    } catch (e) { paused.current = true; setError((e as Error).message) }
    finally { setSaving(false) }
  }
  return <section className="space-y-4" aria-label="ผลเปรียบเทียบ">
    <div className="card"><div className="flex flex-wrap justify-between gap-3"><div><p className="eyebrow">ผลการตรวจเอกสาร</p><h2 className="text-xl mt-1">{dirty ? saving ? 'กำลังเทียบค่าใหม่…' : error ? 'บันทึกค่าไม่สำเร็จ' : 'กำลังเทียบค่าอัตโนมัติ…' : statusLabels[result.status]}</h2></div><Badge status={dirty ? 'review' : result.status} /></div>
      <p className="muted text-sm mt-2">{new Date(value.created_at).toLocaleString('th-TH')} · {value.reviewed ? 'ตรวจทานแล้ว' : 'ผลอัตโนมัติ'}{value.edited ? ' · แก้จาก OCR' : ''} · รุ่น {value.revision}</p>
      {dirty && <p className={error ? 'error mt-3' : 'notice mt-3'} role={error ? 'alert' : 'status'} aria-live="polite">{error || (saving ? 'กำลังบันทึกและคำนวณผลใหม่…' : 'ระบบจะบันทึกและคำนวณให้อัตโนมัติ')}</p>}
      {error && <button className="secondary mt-2" type="button" onClick={() => { paused.current = false; setError(''); setRetry(v => v + 1) }}>ลองบันทึกอีกครั้ง</button>}
      {!dirty && <>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-5"><div className={`summary-box comparison-${result.po_status}`}><span>เลขอ้างอิง PO</span><Badge status={result.po_status} /><p className="mt-3 font-mono break-all">{result.checking_po_normalized || 'ไม่พบ'} ↔ {result.invoice_po_normalized || 'ไม่พบ'}</p></div><div className={`summary-box comparison-${result.qty_status}`}><span>จำนวนสินค้า QTY</span><Badge status={result.qty_status} /><p className="text-sm mt-3">{value.documents.map(d => d.current.items.map(item => `${item.qty} ${item.uom}`).join(', ') || 'ไม่พบ').join(' ↔ ')}</p></div></div>
      {result.reasons.map(reason => <p key={reason} className="notice mt-3">{reason}</p>)}
      <div className="overflow-x-auto mt-4"><table><caption className="sr-only">ผลเทียบจำนวนสินค้า</caption><thead><tr><th>รหัสสินค้า</th><th>Checksheet</th><th>Invoice</th><th>ผล</th></tr></thead><tbody>{result.rows.map((row, index) => <tr key={index}><td>{row.code || '—'}</td><td>{row.checking_qty} {row.checking_uom}</td><td>{row.invoice_qty} {row.invoice_uom}</td><td><Badge status={row.status} /></td></tr>)}</tbody></table></div>
      {!result.rows.length && <p className="muted py-4">ยังจับคู่รายการไม่ได้ ตรวจและแก้รายการในแผงด้านล่าง</p>}
      </>}
    </div>
    <details className="result-editor card" open={editorOpen} onToggle={event => onEditorToggle?.(event.currentTarget.open)}>
      <summary>ดูข้อมูลที่อ่านได้ / แก้ไขข้อมูล</summary>
      <p className="muted text-sm mb-3">แก้ค่าแล้วระบบบันทึกและเทียบใหม่ให้อัตโนมัติ</p>
      <fieldset disabled={saving} className="grid md:grid-cols-2 gap-4">
        {value.documents.map(document => <section className="card" key={document.kind}>
          <h3 className="font-bold">ตรวจค่า {titles[document.kind]}</h3><p className="muted text-xs break-all mt-1">{document.filename}</p>
          <label className="field mt-4">เลขอ้างอิง PO<input required maxLength={100} value={drafts[document.kind].po} onChange={e => change(document.kind, d => ({ ...d, po: e.target.value }))} /></label>
          <p className="muted text-xs mt-2">OCR ดิบ: {document.original.po || 'ไม่พบ'} · {document.original.po_source || 'ไม่พบ label'} · ความเชื่อมั่น {Math.round(document.original.po_confidence * 100)}%</p>
          {drafts[document.kind].items.map((item, index) => <div className="item-edit" key={index}>
            <label className="field">รหัสสินค้า / Barcode<input maxLength={100} value={item.code} onChange={e => change(document.kind, d => ({ ...d, items: d.items.map((v, i) => i === index ? { ...v, code: e.target.value } : v) }))} /></label>
            <div className="grid grid-cols-2 gap-2 mt-2"><label className="field">จำนวน QTY<input required maxLength={40} inputMode="decimal" value={item.qty} onChange={e => change(document.kind, d => ({ ...d, items: d.items.map((v, i) => i === index ? { ...v, qty: e.target.value } : v) }))} /></label><label className="field">หน่วย UOM<input required maxLength={20} value={item.uom} onChange={e => change(document.kind, d => ({ ...d, items: d.items.map((v, i) => i === index ? { ...v, uom: e.target.value } : v) }))} /></label></div>
            <p className="muted text-xs mt-2 break-words">{item.source || 'เพิ่มโดยผู้ใช้'}{item.confidence > 0 ? ` · ${Math.round(item.confidence * 100)}%` : ''}</p>
            <button className="text-button" type="button" onClick={() => change(document.kind, d => ({ ...d, items: d.items.filter((_, i) => i !== index) }))}>ลบรายการ {index + 1}</button>
          </div>)}
          <button className="secondary w-full mt-3" type="button" disabled={drafts[document.kind].items.length >= 200} onClick={() => change(document.kind, d => ({ ...d, items: [...d.items, { code: '', qty: '', uom: '', source: 'เพิ่มโดยผู้ใช้', confidence: 0 }] }))}>+ เพิ่มรายการสินค้า</button>
          {document.original.warnings.map(message => <p className="notice mt-3" key={message}>{message}</p>)}
          <details className="mt-4"><summary>ดูข้อความ OCR และหลักฐานต้นฉบับ</summary><pre>{document.ocr_text || 'ไม่พบข้อความ'}</pre><h4 className="text-sm font-bold mt-3">ค่าดิบที่สกัดได้</h4><pre>{JSON.stringify(document.original, null, 2)}</pre><ul className="evidence">{document.evidence.map((line, index) => <li key={index}><span>หน้า {line.page} · {Math.round(line.confidence * 100)}%</span> {line.text}<small>ตำแหน่ง: {line.box.map(point => point.map(n => Math.round(n)).join(',')).join(' / ') || 'ไม่มีข้อมูล'}</small></li>)}</ul></details>
        </section>)}
      </fieldset>
    </details>
    </section>
}

export function ScanAnimation({ files }: { files: Partial<Record<Kind, File>> }) {
  const urls = useMemo(() => Object.values(files).filter(file => !/\.pdf$/i.test(file.name)).map(file => URL.createObjectURL(file)), [files])
  useEffect(() => () => urls.forEach(url => URL.revokeObjectURL(url)), [urls])
  return <div className="scan-animation" aria-hidden="true">{urls.map(url => <div className="scan-frame" key={url}><img src={url} alt="" /><span /></div>)}</div>
}
