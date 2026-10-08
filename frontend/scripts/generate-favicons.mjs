/**
 * Generates the raster SkyStay favicon assets from the same geometry used by
 * `public/favicon.svg`, so the browser-tab icon and the PNG/ICO fallbacks can
 * never drift apart.
 *
 * Run from `frontend/` with:  node scripts/generate-favicons.mjs
 *
 * Outputs (all committed, so a plain `npm install && npm run dev` needs no
 * extra step):
 *   public/favicon-32.png       32x32   modern browsers / tab icon
 *   public/apple-touch-icon.png 180x180 iOS home screen
 *   public/favicon.ico          32x32   classic fallback (PNG-compressed ICO)
 *
 * The design mirrors the app's own brand mark (`.header__brand-mark`): a gold
 * rounded tile carrying the navy compass glyph used across the site.
 */

import { deflateSync } from 'node:zlib'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const OUT_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'public')

/* --- design, expressed in a 64x64 grid (matches favicon.svg) --------------- */

const NAVY = [6, 21, 38] // --navy-900
const GOLD_LIGHT = [220, 184, 74] // --gold-400
const GOLD_DARK = [169, 134, 26] // --gold-600

const TILE_RADIUS = 14
const RING_CENTER = 32
const RING_RADIUS = 17
const RING_STROKE = 3.4
// The needle is the compass glyph from components/Icon.jsx, scaled 24 -> 64.
const NEEDLE = [
  [41.333, 22.667],
  [36, 36],
  [22.667, 41.333],
  [28, 28],
]

/* --- rasteriser ----------------------------------------------------------- */

/** Signed test for a rounded rectangle covering the full 64x64 canvas. */
function insideTile(x, y) {
  const r = TILE_RADIUS
  const cx = Math.min(Math.max(x, r), 64 - r)
  const cy = Math.min(Math.max(y, r), 64 - r)
  return (x - cx) ** 2 + (y - cy) ** 2 <= r * r
}

/** True when the point falls on the compass ring stroke. */
function onRing(x, y) {
  const distance = Math.hypot(x - RING_CENTER, y - RING_CENTER)
  return Math.abs(distance - RING_RADIUS) <= RING_STROKE / 2
}

/** Even-odd point-in-polygon test for the compass needle. */
function insideNeedle(x, y) {
  let inside = false
  for (let i = 0, j = NEEDLE.length - 1; i < NEEDLE.length; j = i++) {
    const [xi, yi] = NEEDLE[i]
    const [xj, yj] = NEEDLE[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

/** Colour + alpha for a point, returned as [r, g, b, a] with a in 0..1. */
function sample(x, y) {
  if (!insideTile(x, y)) return [0, 0, 0, 0]

  if (onRing(x, y) || insideNeedle(x, y)) return [...NAVY, 1]

  // Diagonal gold gradient, matching linear-gradient(135deg, gold-400, gold-600).
  const t = Math.min(1, Math.max(0, (x + y) / 128))
  return [
    Math.round(GOLD_LIGHT[0] + (GOLD_DARK[0] - GOLD_LIGHT[0]) * t),
    Math.round(GOLD_LIGHT[1] + (GOLD_DARK[1] - GOLD_LIGHT[1]) * t),
    Math.round(GOLD_LIGHT[2] + (GOLD_DARK[2] - GOLD_LIGHT[2]) * t),
    1,
  ]
}

/** Renders an RGBA buffer at `size`, supersampled 4x4 for smooth edges. */
function render(size) {
  const scale = 64 / size
  const pixels = Buffer.alloc(size * size * 4)
  const SUB = 4

  for (let py = 0; py < size; py += 1) {
    for (let px = 0; px < size; px += 1) {
      let r = 0
      let g = 0
      let b = 0
      let a = 0
      for (let sy = 0; sy < SUB; sy += 1) {
        for (let sx = 0; sx < SUB; sx += 1) {
          const x = (px + (sx + 0.5) / SUB) * scale
          const y = (py + (sy + 0.5) / SUB) * scale
          const [cr, cg, cb, ca] = sample(x, y)
          // Premultiply so partially covered edge pixels blend correctly.
          r += cr * ca
          g += cg * ca
          b += cb * ca
          a += ca
        }
      }
      const samples = SUB * SUB
      const alpha = a / samples
      const offset = (py * size + px) * 4
      pixels[offset] = alpha ? Math.round(r / a) : 0
      pixels[offset + 1] = alpha ? Math.round(g / a) : 0
      pixels[offset + 2] = alpha ? Math.round(b / a) : 0
      pixels[offset + 3] = Math.round(alpha * 255)
    }
  }
  return pixels
}

/* --- PNG encoding --------------------------------------------------------- */

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})

function crc32(buffer) {
  let c = 0xffffffff
  for (const byte of buffer) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length)
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data])
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(body))
  return Buffer.concat([length, body, crc])
}

function encodePng(size, pixels) {
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8 // bit depth
  ihdr[9] = 6 // colour type: RGBA
  // bytes 10-12 stay 0 (deflate, adaptive filtering, no interlace)

  // Prefix every scanline with filter type 0 (None).
  const stride = size * 4
  const raw = Buffer.alloc((stride + 1) * size)
  for (let y = 0; y < size; y += 1) {
    raw[y * (stride + 1)] = 0
    pixels.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride)
  }

  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ])
}

/** Wraps a PNG as a single-image ICO (supported by every modern browser). */
function encodeIco(png, size) {
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0) // reserved
  header.writeUInt16LE(1, 2) // type: icon
  header.writeUInt16LE(1, 4) // image count

  const entry = Buffer.alloc(16)
  entry[0] = size >= 256 ? 0 : size
  entry[1] = size >= 256 ? 0 : size
  entry[2] = 0 // palette size
  entry[3] = 0 // reserved
  entry.writeUInt16LE(1, 4) // colour planes
  entry.writeUInt16LE(32, 6) // bits per pixel
  entry.writeUInt32LE(png.length, 8)
  entry.writeUInt32LE(header.length + entry.length, 12)

  return Buffer.concat([header, entry, png])
}

/* --- main ----------------------------------------------------------------- */

mkdirSync(OUT_DIR, { recursive: true })

const png32 = encodePng(32, render(32))
const png180 = encodePng(180, render(180))

writeFileSync(resolve(OUT_DIR, 'favicon-32.png'), png32)
writeFileSync(resolve(OUT_DIR, 'apple-touch-icon.png'), png180)
writeFileSync(resolve(OUT_DIR, 'favicon.ico'), encodeIco(png32, 32))

console.log('Wrote favicon-32.png, apple-touch-icon.png and favicon.ico to public/')
