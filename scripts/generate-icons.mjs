// Dependency-free rasterization of our geometric app mark for Android PWA icons.
import { deflateSync } from 'node:zlib';
import { writeFileSync } from 'node:fs';

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function chunk(name, data) {
  const body = Buffer.concat([Buffer.from(name), data]);
  const size = Buffer.alloc(4); size.writeUInt32BE(data.length);
  const checksum = Buffer.alloc(4); checksum.writeUInt32BE(crc32(body));
  return Buffer.concat([size, body, checksum]);
}
function segmentDistance(x, y, ax, ay, bx, by) {
  const t = Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)));
  return Math.hypot(x - ax - t * (bx - ax), y - ay - t * (by - ay));
}
for (const size of [192, 512]) {
  const raw = Buffer.alloc((size * 3 + 1) * size);
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    const px = x / size * 512, py = y / size * 512;
    let color = [0, 128, 198];
    if (px > 136 && px < 376 && py > 105 && py < 407) color = [255, 255, 255];
    if (segmentDistance(px, py, 184, 174, 328, 174) < 10 || segmentDistance(px, py, 184, 220, 280, 220) < 10) color = [236, 137, 34];
    if (segmentDistance(px, py, 192, 310, 234, 352) < 12 || segmentDistance(px, py, 234, 352, 324, 252) < 12) color = [0, 128, 198];
    raw.set(color, y * (size * 3 + 1) + 1 + x * 3);
  }
  const header = Buffer.alloc(13); header.writeUInt32BE(size, 0); header.writeUInt32BE(size, 4); header[8] = 8; header[9] = 2;
  writeFileSync(new URL(`../frontend/public/icon-${size}.png`, import.meta.url), Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', header), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]));
}
console.log('Generated PWA icons: 192px, 512px');
