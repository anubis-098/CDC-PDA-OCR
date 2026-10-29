import { useEffect, useRef, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import { browserCamera } from '../camera'
import { titles, type Kind } from '../types'

export function CaptureCard({ kind, file, onChange, disabled, actionLabel, actionVariant }: { kind: Kind; file?: File; onChange: (file: File) => void; disabled: boolean; actionLabel?: string; actionVariant?: 'success' | 'primary' }) {
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const generation = useRef(0)
  const [active, setActive] = useState(false)
  const [opening, setOpening] = useState(false)
  const [candidate, setCandidate] = useState<File>()
  const [preview, setPreview] = useState('')
  const [error, setError] = useState('')
  const shown = candidate || file
  const pdf = shown?.type === 'application/pdf' || shown?.name.toLowerCase().endsWith('.pdf')

  const stop = () => {
    generation.current++
    if (stream.current) browserCamera.stop(stream.current)
    stream.current = null
    setActive(false); setOpening(false)
  }
  useEffect(() => () => { generation.current++; if (stream.current) browserCamera.stop(stream.current) }, [])
  useEffect(() => {
    if (!shown) { setPreview(''); return }
    const url = URL.createObjectURL(shown); setPreview(url)
    return () => URL.revokeObjectURL(url)
  }, [shown])
  useEffect(() => {
    if (active && video.current && stream.current) {
      video.current.srcObject = stream.current
      void video.current.play().catch(() => { setError('แสดงกล้องไม่ได้ กรุณาลองใหม่'); stop() })
    }
  }, [active])
  useEffect(() => {
    const hidden = () => { if (document.hidden) stop() }
    document.addEventListener('visibilitychange', hidden)
    return () => document.removeEventListener('visibilitychange', hidden)
  }, [])
  useEffect(() => { if (disabled) stop() }, [disabled])

  async function open() {
    stop(); setError(''); setCandidate(undefined); setOpening(true)
    const token = generation.current
    try {
      const next = await browserCamera.open()
      if (token !== generation.current) { browserCamera.stop(next); return }
      stream.current = next; setActive(true)
    } catch (e) { if (token === generation.current) setError((e as Error).message) }
    finally { if (token === generation.current) setOpening(false) }
  }
  async function capture() {
    try { if (video.current) { setCandidate(await browserCamera.capture(video.current)); stop() } }
    catch (e) { setError((e as Error).message) }
  }
  function select(next?: File) {
    if (!next) return
    stop(); setError('')
    if (next.size > 10 * 1024 * 1024) { setError('แต่ละไฟล์ต้องไม่เกิน 10 MB'); return }
    if (!/\.(jpe?g|png|pdf)$/i.test(next.name)) { setError('รองรับ JPG, JPEG, PNG และ PDF'); return }
    setCandidate(next)
  }

  return <section className="card capture-card">
    <div className="flex items-center gap-3"><span className="step">{kind === 'checking' ? '1' : '2'}</span><div><h2>{titles[kind]}</h2><p className="muted text-sm">{kind === 'checking' ? 'ใบตรวจรับสินค้า · จำนวนแผนรับ' : 'ใบแจ้งหนี้ · จำนวนที่ส่ง'}</p></div>{file && <span className="ml-auto text-teal-700 text-sm">พร้อม ✓</span>}</div>
    <div className="capture-preview">
      {active ? <><video ref={video} autoPlay playsInline muted aria-label={`กล้อง ${titles[kind]}`} /><div className="camera-frame" /></> : preview ? pdf ? <div className="text-center p-5"><span className="document-symbol">PDF</span><p className="break-all">{shown?.name}</p><a href={preview} target="_blank" rel="noreferrer">เปิดดูเอกสาร PDF ↗</a></div> : <a href={preview} target="_blank" rel="noreferrer" aria-label="เปิดภาพขนาดเต็ม"><img src={preview} alt={`ภาพ ${titles[kind]}`} /></a> : <div className="text-center p-5"><span className="document-symbol">▤</span><p>ยังไม่ได้เลือกเอกสาร</p><p className="muted text-sm mt-1">วางกระดาษให้เรียบ ถ่ายให้ครบหน้า<br />หลีกเลี่ยงเงาและแสงสะท้อน</p></div>}
    </div>
    {error && <p className="error mb-3" role="alert">{error}</p>}
    {active ? <div className="grid grid-cols-2 gap-2"><button onClick={capture}>จับภาพ</button><button className="secondary" onClick={stop}>ยกเลิก</button></div> : candidate ? <div className="capture-actions"><button className={`capture-accept w-full ${actionVariant === 'success' ? 'success-action' : ''}`} disabled={disabled} onClick={() => { onChange(candidate); setCandidate(undefined) }}>{actionLabel || `ใช้${pdf ? 'ไฟล์' : 'ภาพ'}นี้`}</button><button disabled={disabled} className="secondary retake-icon" aria-label={pdf ? 'เลือกเอกสารใหม่' : 'ถ่ายใหม่'} title={pdf ? 'เลือกเอกสารใหม่' : 'ถ่ายใหม่'} onClick={() => { setCandidate(undefined); if (!pdf) void open() }}><RefreshCw size={20} strokeWidth={2} aria-hidden="true" /></button></div> : <><button className="w-full" disabled={disabled || opening} onClick={() => void open()}>{opening ? 'กำลังเปิดกล้อง…' : `${file ? 'ถ่ายใหม่' : 'ถ่าย'} ${titles[kind]}`}</button>{file && !opening && <button className="secondary w-full mt-2" disabled={disabled} onClick={() => onChange(file)}>{actionLabel || 'ใช้เอกสารเดิม'}</button>}</>}
    {opening && <button className="secondary w-full mt-2" onClick={stop}>ยกเลิกเปิดกล้อง</button>}
    <label className={`file-button mt-2 ${disabled ? 'disabled' : ''}`}>เลือกรูปจากอุปกรณ์ / PDF<input type="file" accept="image/jpeg,image/png,application/pdf" disabled={disabled} onChange={e => { select(e.target.files?.[0]); e.target.value = '' }} /></label>
    {file && <p className="muted text-xs mt-2 break-all">เลือกแล้ว: {file.name}</p>}
  </section>
}
