export type Kind = 'checking' | 'invoice'
export type Status = 'match' | 'mismatch' | 'unit_mismatch' | 'review'
export const statusLabels: Record<Status, string> = {
  match: 'ตรงกัน', mismatch: 'ไม่ตรงกัน', unit_mismatch: 'หน่วยไม่ตรงกัน', review: 'ต้องตรวจทาน',
}
export const titles: Record<Kind, string> = { checking: 'Checking Sheet', invoice: 'Invoice' }
export interface Item { code: string; qty: string; uom: string; source: string; confidence: number }
export interface Extracted { po: string; po_source: string; po_confidence: number; items: Item[]; warnings: string[] }
export interface Evidence { text: string; confidence: number; page: number; box: number[][] }
export interface Document { kind: Kind; filename: string; ocr_text: string; original: Extracted; current: Extracted; evidence: Evidence[] }
export interface Row { code: string; checking_qty: string; invoice_qty: string; checking_normalized: string | null; invoice_normalized: string | null; checking_uom: string; invoice_uom: string; status: Status }
export interface Comparison {
  id: string; created_at: string; updated_at: string; revision: number; reviewed: boolean; edited: boolean; documents: Document[]
  result: { status: Status; po_status: Status; qty_status: Status; checking_po_normalized: string; invoice_po_normalized: string; reasons: string[]; rows: Row[] }
}
export interface History { page: number; page_size: number; total: number; items: { id: string; created_at: string; reviewed: boolean; status: Status; po: string }[] }
