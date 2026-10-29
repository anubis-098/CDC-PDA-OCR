export interface CameraAdapter {
  open(): Promise<MediaStream>
  capture(video: HTMLVideoElement): Promise<File>
  stop(stream: MediaStream): void
}

export const browserCamera: CameraAdapter = {
  async open() {
    if (!window.isSecureContext) throw new Error('กล้องต้องใช้ HTTPS กรุณาเปิด URL ที่ปลอดภัย หรือเลือกรูปจากอุปกรณ์')
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('เบราว์เซอร์นี้ไม่รองรับกล้อง กรุณาเลือกรูปจากอุปกรณ์')
    try {
      return await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: 'environment' }, width: { ideal: 2400 }, height: { ideal: 1800 } } })
    } catch (error) {
      const name = (error as DOMException).name
      if (name === 'NotAllowedError') throw new Error('ไม่ได้รับสิทธิ์กล้อง เปิดสิทธิ์กล้องในการตั้งค่าเว็บไซต์ หรือเลือกรูปจากอุปกรณ์')
      if (name === 'NotFoundError') throw new Error('ไม่พบกล้อง กรุณาเลือกรูปจากอุปกรณ์')
      throw new Error('เปิดกล้องไม่ได้ ปิดแอปที่ใช้กล้องอยู่แล้วลองใหม่ หรือเลือกไฟล์')
    }
  },
  async capture(video) {
    if (!video.videoWidth) throw new Error('กล้องยังไม่พร้อม กรุณารอสักครู่')
    const scale = Math.min(1, 2400 / Math.max(video.videoWidth, video.videoHeight))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale)
    const context = canvas.getContext('2d')
    if (!context) throw new Error('ไม่สามารถจับภาพได้ กรุณาเลือกไฟล์แทน')
    context.drawImage(video, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob(value => value ? resolve(value) : reject(new Error('บันทึกภาพไม่สำเร็จ')), 'image/jpeg', 0.92))
    return new File([blob], `capture-${Date.now()}.jpg`, { type: 'image/jpeg' })
  },
  stop(stream) { stream.getTracks().forEach(track => track.stop()) },
}
