import type { Comparison, History } from './types'

function errorMessage(body: unknown): string {
  const detail = (body as { detail?: unknown })?.detail
  return typeof detail === 'string' ? detail : 'ข้อมูลไม่ถูกต้อง กรุณาตรวจ PO จำนวน และหน่วยให้ครบ'
}

export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(`/api${path}`, options) }
  catch { throw new Error('เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ ตรวจเครือข่ายแล้วลองใหม่') }
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body ? errorMessage(body) : `เซิร์ฟเวอร์ไม่พร้อม (${response.status}) กรุณาลองใหม่`)
  }
  return response.json() as Promise<T>
}

export const getHistory = (page: number) => request<History>(`/comparisons?page=${page}`)
export const getComparison = (id: string) => request<Comparison>(`/comparisons/${id}`)

export function uploadDocuments(checking: File, invoice: File, progress: (message: string) => void): Promise<Comparison> {
  return new Promise((resolve, reject) => {
    const body = new FormData()
    body.append('checking', checking); body.append('invoice', invoice)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/comparisons')
    xhr.timeout = 600000
    xhr.upload.onprogress = event => progress(event.lengthComputable ? `กำลังส่งภาพ ${Math.round(event.loaded / event.total * 100)}%` : 'กำลังส่งภาพ…')
    xhr.upload.onload = () => progress('กำลังอ่านเอกสาร… ครั้งแรกอาจใช้เวลาดาวน์โหลดโมเดล')
    xhr.onload = () => {
      let data: unknown
      try { data = JSON.parse(xhr.responseText) } catch { reject(new Error('เซิร์ฟเวอร์ตอบกลับไม่สำเร็จ กรุณาลองใหม่')); return }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data as Comparison)
      else reject(new Error(errorMessage(data)))
    }
    xhr.onerror = () => reject(new Error('ส่งภาพไม่สำเร็จ ตรวจเครือข่ายแล้วลองใหม่ ภาพยังอยู่ในหน้านี้'))
    xhr.ontimeout = () => reject(new Error('ใช้เวลานานเกินไป กรุณาตรวจประวัติก่อนลองส่งใหม่'))
    xhr.send(body)
  })
}
