/**
 * 카메라 프레임 + MediaPipe 얼굴/손/포즈 노드·엣지 오버레이.
 * contain letterbox 로 잘림 없이 비디오와 랜드마크를 동일 좌표계로 그림.
 */

export interface OverlayPt {
  x: number
  y: number
}

export const HAND_EDGES: ReadonlyArray<readonly [number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [0, 9], [9, 10], [10, 11], [11, 12],
  [0, 13], [13, 14], [14, 15], [15, 16],
  [0, 17], [17, 18], [18, 19], [19, 20],
  [5, 9], [9, 13], [13, 17],
]

/** MediaPipe Pose 33 — 몸통/팔/다리 골격 */
export const POSE_EDGES: ReadonlyArray<readonly [number, number]> = [
  // torso
  [11, 12], [11, 23], [12, 24], [23, 24],
  // arms
  [11, 13], [13, 15], [12, 14], [14, 16],
  // hands rough
  [15, 17], [15, 19], [15, 21], [16, 18], [16, 20], [16, 22],
  // legs
  [23, 25], [25, 27], [27, 29], [27, 31],
  [24, 26], [26, 28], [28, 30], [28, 32],
  // face-ish
  [11, 7], [12, 8], [7, 3], [8, 3], [3, 0],
]

export const FACE_EDGES: ReadonlyArray<readonly [number, number]> = [
  [10, 338], [338, 297], [297, 332], [332, 284], [284, 251], [251, 389],
  [389, 356], [356, 454], [454, 323], [323, 361], [361, 288], [288, 397],
  [397, 365], [365, 379], [379, 378], [378, 400], [400, 377], [377, 152],
  [152, 148], [148, 176], [176, 149], [149, 150], [150, 136], [136, 172],
  [172, 58], [58, 132], [132, 93], [93, 234], [234, 127], [127, 162],
  [162, 21], [21, 54], [54, 103], [103, 67], [67, 109], [109, 10],
  [33, 7], [7, 163], [163, 144], [144, 145], [145, 153], [153, 154],
  [154, 155], [155, 133], [33, 246], [246, 161], [161, 160], [160, 159],
  [159, 158], [158, 157], [157, 173], [173, 133],
  [362, 382], [382, 381], [381, 380], [380, 374], [374, 373], [373, 390],
  [390, 249], [249, 263], [362, 398], [398, 384], [384, 385], [385, 386],
  [386, 387], [387, 388], [388, 466], [466, 263],
  [61, 146], [146, 91], [91, 181], [181, 84], [84, 17], [17, 314],
  [314, 405], [405, 321], [321, 375], [375, 291], [61, 185], [185, 40],
  [40, 39], [39, 37], [37, 0], [0, 267], [267, 269], [269, 270],
  [270, 409], [409, 291],
]

export function fitContain(
  srcW: number,
  srcH: number,
  dstW: number,
  dstH: number,
): { x: number; y: number; w: number; h: number } {
  if (srcW <= 0 || srcH <= 0) return { x: 0, y: 0, w: dstW, h: dstH }
  const s = Math.min(dstW / srcW, dstH / srcH)
  const w = srcW * s
  const h = srcH * s
  return { x: (dstW - w) / 2, y: (dstH - h) / 2, w, h }
}

export function drawTrackingOverlay(
  ctx: CanvasRenderingContext2D,
  opts: {
    w: number
    h: number
    video: HTMLVideoElement | null
    face: OverlayPt[] | null
    hands: OverlayPt[][]
    pose: OverlayPt[] | null
    mirror?: boolean
  },
): void {
  const { w, h, video, face, hands, pose, mirror = true } = opts
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = '#0b0d14'
  ctx.fillRect(0, 0, w, h)

  const vw = video?.videoWidth ?? 0
  const vh = video?.videoHeight ?? 0
  const box = vw > 0 && vh > 0 ? fitContain(vw, vh, w, h) : { x: 0, y: 0, w, h }

  if (video && vw > 0 && video.readyState >= 2) {
    ctx.save()
    if (mirror) {
      ctx.translate(box.x + box.w, box.y)
      ctx.scale(-1, 1)
      ctx.drawImage(video, 0, 0, box.w, box.h)
    } else {
      ctx.drawImage(video, box.x, box.y, box.w, box.h)
    }
    ctx.restore()
  }

  const px = (p: OverlayPt) => {
    const nx = mirror ? 1 - p.x : p.x
    return { x: box.x + nx * box.w, y: box.y + p.y * box.h }
  }

  const drawEdges = (
    pts: OverlayPt[],
    edges: ReadonlyArray<readonly [number, number]>,
    color: string,
    width: number,
  ) => {
    ctx.strokeStyle = color
    ctx.lineWidth = width
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.beginPath()
    for (const [a, b] of edges) {
      if (a >= pts.length || b >= pts.length) continue
      const pa = px(pts[a])
      const pb = px(pts[b])
      ctx.moveTo(pa.x, pa.y)
      ctx.lineTo(pb.x, pb.y)
    }
    ctx.stroke()
  }

  const drawNodes = (pts: OverlayPt[], color: string, r: number, step = 1) => {
    ctx.fillStyle = color
    for (let i = 0; i < pts.length; i += step) {
      const q = px(pts[i])
      ctx.beginPath()
      ctx.arc(q.x, q.y, r, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // pose skeleton under face/hands
  if (pose && pose.length >= 25) {
    drawEdges(pose, POSE_EDGES, 'rgba(255, 210, 80, 0.9)', 2.2)
    drawNodes(pose, 'rgba(255, 220, 100, 0.95)', 2.8, 1)
  }

  if (face && face.length > 0) {
    drawNodes(face, 'rgba(120, 220, 255, 0.65)', 1.3, 2)
    drawEdges(face, FACE_EDGES, 'rgba(80, 200, 255, 0.9)', 1.4)
  }

  const handColors = ['#ff5aa0', '#78ff9f']
  hands.forEach((hand, i) => {
    if (!hand || hand.length < 21) return
    const col = handColors[i % handColors.length]
    drawEdges(hand, HAND_EDGES, col, 2.4)
    drawNodes(hand, col, 2.8, 1)
  })

  ctx.strokeStyle = 'rgba(255,255,255,0.22)'
  ctx.lineWidth = 1
  ctx.strokeRect(box.x + 0.5, box.y + 0.5, box.w - 1, box.h - 1)
}
