import { useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { getComparison, getHistory, uploadDocuments } from './api'
import { CaptureCard } from './components/CaptureCard'
import { Badge, OCRReview, Results, ScanAnimation } from './components/Results'
import type { Comparison, History, Kind } from './types'

type Stage = 'checking' | 'invoice' | 'processing' | 'result'

export default function App() {
  const [stage, setStage] = useState<Stage>('checking')
  const [files, setFiles] = useState<Partial<Record<Kind, File>>>({})
  const [result, setResult] = useState<Comparison>()
  const [history, setHistory] = useState<History>()
  const [page, setPage] = useState(1)
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editorOpen, setEditorOpen] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [historyError, setHistoryError] = useState('')
  const [historyBusy, setHistoryBusy] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  const [refresh, setRefresh] = useState(0)
  const inFlight = useRef(false)
  const heading = useRef<HTMLHeadingElement>(null)
  const step = stage === 'checking' ? 1 : stage === 'invoice' ? 2 : 3

  useEffect(() => {
    const update = () => setOnline(navigator.onLine)
    window.addEventListener('online', update); window.addEventListener('offline', update)
    return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) }
  }, [])
  useEffect(() => {
    heading.current?.focus({ preventScroll: true })
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [stage])
  useEffect(() => {
    if (!historyOpen) return
    let ignore = false
    setHistoryBusy(true); setHistoryError('')
    getHistory(page).then(value => { if (!ignore) setHistory(value) }).catch(e => { if (!ignore) setHistoryError(e.message) }).finally(() => { if (!ignore) setHistoryBusy(false) })
    return () => { ignore = true }
  }, [page, refresh, historyOpen])

  async function submit(checking = files.checking, invoice = files.invoice) {
    if (!checking || !invoice || inFlight.current) return
    setStage('processing'); setError(''); setResult(undefined); setEditorOpen(false)
    if (!navigator.onLine) { setError('เชื่อมต่อเครือข่ายแล้วกดลองอีกครั้ง ภาพทั้งสองใบยังอยู่'); return }
    inFlight.current = true
    setBusy(true); setStatus('กำลังส่งภาพ…')
    try {
      setResult(await uploadDocuments(checking, invoice, setStatus))
      setPage(1); setRefresh(v => v + 1); setStage('result'); setStatus('')
    } catch (e) { setError((e as Error).message); setStatus('') }
    finally { inFlight.current = false; setBusy(false) }
  }
  function accept(kind: Kind, file: File) {
    setFiles(previous => ({ ...previous, [kind]: file })); setError(''); setStatus('')
    if (kind === 'checking') setStage('invoice')
    else void submit(files.checking, file)
  }
  function startNew() {
    setFiles({}); setResult(undefined); setError(''); setStatus(''); setHistoryOpen(false); setEditorOpen(false); setStage('checking')
  }
  async function openHistory(id: string) {
    if (inFlight.current) return
    inFlight.current = true; setBusy(true); setError(''); setStatus('กำลังเปิดประวัติ…')
    try { setResult(await getComparison(id)); setFiles({}); setHistoryOpen(false); setEditorOpen(false); setStage('result'); setStatus('') }
    catch (e) { setError((e as Error).message); setStatus('') }
    finally { inFlight.current = false; setBusy(false) }
  }

  return <>
    <header className="site-header"><div className="max-w-5xl mx-auto px-4 py-4 flex items-center gap-4"><img className="company-logo" src="/cj-logistics.svg" alt="CJ Logistics" width="205" height="50" /><div className="header-product"><div className="flex flex-wrap items-center justify-between gap-2"><h1 className="font-bold text-lg">ตรวจรับ</h1><span className={`connection-status ${online ? 'is-online' : ''}`}>{online ? '● ออนไลน์' : '○ ออฟไลน์'}</span></div><p className="header-caption">PDA DOCUMENT CHECK</p></div></div></header>
    <main className="app-main wizard-main mx-auto px-4 py-6 space-y-4">
      <nav aria-label="ขั้นตอนตรวจเอกสาร"><ol className="wizard-steps">{['Checksheet', 'Invoice', 'ผลสแกน'].map((label, index) => <li key={label} className={step === index + 1 ? 'current' : step > index + 1 ? 'complete' : ''} aria-current={step === index + 1 ? 'step' : undefined}><span className="wizard-number" aria-hidden="true">{step > index + 1 ? '✓' : index + 1}</span><span>{label}</span></li>)}</ol></nav>
      <section className="intro"><p className="eyebrow">ขั้นตอน {step} จาก 3</p><h2 ref={heading} tabIndex={-1} className="text-2xl font-bold mt-1">{stage === 'checking' ? 'ถ่าย Checksheet ก่อน' : stage === 'invoice' ? 'ต่อไป ถ่าย Invoice' : stage === 'processing' ? error ? 'ยังอ่านเอกสารไม่สำเร็จ' : 'กำลังอ่านเอกสาร' : 'สรุปผลการตรวจ'}</h2><p className="muted mt-1">{stage === 'checking' ? 'ถ่ายใบตรวจรับสินค้าให้ครบหน้าและตัวเลขชัดเจน' : stage === 'invoice' ? 'ใช้ใบแจ้งหนี้ของสินค้าชุดเดียวกับ Checksheet' : stage === 'processing' ? 'เมื่ออ่านเสร็จจะแสดงข้อความ OCR ที่ตำแหน่งบนภาพ' : 'เทียบ PO และจำนวนสินค้าให้แล้ว บันทึกผลอัตโนมัติ'}</p></section>
      {!online && <p className="notice" role="status">ไม่มีเครือข่าย — เลือกภาพไว้ได้ แล้วเชื่อมต่อเพื่ออ่านเอกสาร</p>}
      {(stage === 'checking' || stage === 'invoice') && <>
        {stage === 'invoice' && <div className="completed-document"><span>✓ Checksheet พร้อมแล้ว</span><button className="secondary" disabled={busy} onClick={() => setStage('checking')}>ย้อนกลับ</button></div>}
        <CaptureCard key={stage} kind={stage} file={files[stage]} disabled={busy} onChange={file => accept(stage, file)} actionLabel={stage === 'checking' ? 'ใช้เอกสารนี้ → ไปถ่าย Invoice' : 'ใช้เอกสารนี้ → อ่านและสรุปผล'} actionVariant={stage === 'checking' ? 'success' : 'primary'} />
        <p className="muted text-xs text-center">รองรับ JPG / PNG / PDF · ไม่เกิน 10 MB ต่อไฟล์</p>
        {status && <p role="status" className="muted">{status}</p>}{error && <p className="error" role="alert">{error}</p>}
      </>}
      {stage === 'processing' && <section className="card processing-card" aria-busy={busy}>
        <div className="processing-symbol" aria-hidden="true">{error ? '!' : '…'}</div>
        {busy && <><ScanAnimation files={files} /><p role="status" aria-live="polite" className="font-bold">{status}</p><p className="muted text-sm mt-2">กรุณาเปิดหน้านี้ไว้ระหว่างประมวลผล</p><progress className="ocr-progress" aria-label="กำลังอ่านเอกสาร" /></>}
        <ul className="ready-documents"><li>✓ Checksheet พร้อมแล้ว</li><li>✓ Invoice พร้อมแล้ว</li></ul>
        {error && <><p className="error text-left" role="alert">{error}</p><button className="w-full mt-3" disabled={!online || busy} onClick={() => void submit()}>ลองอ่านอีกครั้ง</button><button className="secondary w-full mt-2" disabled={busy} onClick={() => { setError(''); setStage('invoice') }}>ย้อนกลับไปแก้ภาพ</button></>}
      </section>}
      {stage === 'result' && result && <>
        <OCRReview value={result} files={files} />
        <Results key={`${result.id}-${result.revision}`} value={result} editorOpen={editorOpen} onEditorToggle={setEditorOpen} onPendingChange={setEditing} onSaved={value => { setResult(value); setEditing(false); setRefresh(v => v + 1) }} />
        <div className="wizard-actions"><button className="w-full" disabled={editing} onClick={startNew}>เริ่มตรวจคู่ถัดไป</button>{files.checking && <button className="secondary w-full mt-2" disabled={editing} onClick={() => { setError(''); setStage('checking') }}>กลับไปแก้ภาพเอกสาร</button>}{editing && <p className="muted text-sm mt-2" role="status">รอให้บันทึกการแก้ไขสำเร็จก่อนเริ่มรายการใหม่</p>}</div>
      </>}
      {stage === 'checking' && <details className="card history-panel" open={historyOpen} onToggle={event => setHistoryOpen(event.currentTarget.open)}><summary className="history-summary"><span>ดูประวัติการตรวจ</span><span className="muted text-sm">{history ? `${history.total} รายการ` : ''}</span></summary><div aria-label="ประวัติการตรวจ"><div className="flex items-center justify-end"><button className="secondary icon-label-button" disabled={historyBusy || busy} onClick={() => setRefresh(v => v + 1)}><RefreshCw size={16} aria-hidden="true" />รีเฟรช</button></div>
        {historyBusy && <p role="status" className="muted py-4">กำลังโหลดประวัติ…</p>}{historyError && <p className="error mt-3">{historyError}</p>}
        {!historyBusy && !historyError && history?.items.length === 0 && <p className="text-center py-8 muted">ยังไม่มีประวัติ เริ่มตรวจคู่แรกได้จากด้านบน</p>}
        {!historyBusy && !historyError && history?.items.map(item => <button className="history-row" key={item.id} disabled={busy} onClick={() => void openHistory(item.id)}><span className="text-left min-w-0"><strong className="block break-all">PO {item.po || 'ยังไม่พบเลขอ้างอิง'}</strong><small>{new Date(item.created_at).toLocaleString('th-TH')}</small></span><Badge status={item.status} /></button>)}
        <div className="flex justify-between items-center mt-4"><button className="secondary" disabled={page <= 1 || historyBusy || busy} onClick={() => setPage(v => v - 1)}>ก่อนหน้า</button><span className="text-sm muted">หน้า {page}</span><button className="secondary" disabled={!history || page * history.page_size >= history.total || historyBusy || busy} onClick={() => setPage(v => v + 1)}>ถัดไป</button></div>
      </div></details>}
      <footer className="text-center text-xs muted pb-4">CS และ MU เป็นคนละหน่วย · ตรวจข้อมูลกับเอกสารจริง</footer>
    </main>
  </>
}
