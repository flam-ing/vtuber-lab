import * as THREE from 'three'
import { createMingo } from './model/index'
import { createTracker } from './tracking/index'
import { createAliveness } from './aliveness/index'
import { neutralFrame, type CursorInfo } from './contract'
import { drawTrackingOverlay } from './tracking/overlay'

const canvas = document.getElementById('stage') as HTMLCanvasElement
const video = document.getElementById('cam') as HTMLVideoElement
const trackPanel = document.getElementById('track-panel') as HTMLDivElement | null
const overlay = document.getElementById('track-overlay') as HTMLCanvasElement | null
const overlayCtx = overlay?.getContext('2d') ?? null
const hud = document.getElementById('track-hud') as HTMLDivElement | null
const panelBadge = document.getElementById('track-panel-badge')

const renderer = new THREE.WebGLRenderer({
  canvas,
  alpha: true,
  antialias: true,
  premultipliedAlpha: true,
  powerPreference: 'low-power',
})
renderer.setClearColor(0x000000, 0) // 완전 투명 배경
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

const scene = new THREE.Scene()

// 원본 fullbody-tracking 레시피: 좁은 FOV(준직교) + 키 기준 전신 프레이밍
const camera = new THREE.PerspectiveCamera(17, 1, 0.1, 100)

const mingo = createMingo()
scene.add(mingo.root)

/** 아바타 줌 (1 = 기본, 클수록 멀리 = 더 작게) */
let avatarZoom = 1.0
let showTrackPanel = true
let showTrackHud = true

/**
 * 전신 프레이밍 — PR 원본 그대로.
 * fitH = height * 1.25 (여유 있게 머리~발), lookY = height * 0.52
 * viewport/scissor/Box3 midY 실험은 하반신만 크게 나와서 제거.
 */
function frameCamera() {
  const w = Math.max(1, window.innerWidth)
  const h = Math.max(1, window.innerHeight)
  renderer.setSize(w, h, false)
  camera.aspect = w / h
  if (typeof camera.clearViewOffset === 'function') camera.clearViewOffset()
  renderer.setScissorTest(false)

  const bodyH = Math.max(0.5, mingo.height || 1.5)
  const lookY = bodyH * 0.52
  // 1.25 = 전신 + 머리/발 여백 (원본 1.06은 창이 좁으면 타이트)
  const fitH = bodyH * 1.25 * Math.max(0.85, avatarZoom)
  const dist = fitH / 2 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))

  camera.position.set(0, lookY, dist)
  camera.lookAt(0, lookY, 0)
  camera.near = 0.1
  camera.far = Math.max(100, dist * 10)
  camera.updateProjectionMatrix()

  console.log(
    '[mingo] frameCamera',
    `bodyH=${bodyH.toFixed(2)} lookY=${lookY.toFixed(2)} dist=${dist.toFixed(2)} fov=${camera.fov}`,
  )
}
frameCamera()
window.addEventListener('resize', () => {
  frameCamera()
  if (!panelUserMoved) placePanelDefault()
})
// VRM 로드 후 실측 높이로 전신 재프레이밍
mingo.ready?.then(() => {
  console.log('[mingo] model ready height=', mingo.height)
  frameCamera()
  placePanelDefault()
})

// ---------- 트래킹 + 생명감 ----------
const tracker = createTracker()
const aliveness = createAliveness()
let trackingUp = false
let camStream: MediaStream | null = null
let camBusy = false
let camWanted = true // visibilitychange로 토글 — await 도중 hide되면 startCam이 스스로 정리

/** OBS 가상캠 대신 내장 MacBook/FaceTime 카메라 우선 */
async function pickVideoDeviceId(): Promise<string | undefined> {
  try {
    const warm = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    for (const t of warm.getTracks()) t.stop()
  } catch {
    /* ignore */
  }
  try {
    const cams = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === 'videoinput')
    console.log('[mingo] cameras:', cams.map((c) => c.label || '(no label)'))
    if (!cams.length) return undefined
    const score = (label: string) => {
      const l = label.toLowerCase()
      if (/obs|virtual|snap|camo|iriun|epoccam/.test(l)) return -100
      if (/facetime|macbook|built-?in|내장/.test(l)) return 100
      return 10
    }
    return [...cams].sort((a, b) => score(b.label) - score(a.label))[0]?.deviceId
  } catch {
    return undefined
  }
}

async function startCam() {
  if (camBusy || trackingUp) return
  camBusy = true
  try {
    const deviceId = await pickVideoDeviceId()
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: deviceId
        ? { deviceId: { exact: deviceId }, width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } }
        : { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 30 } },
    })
    if (!camWanted) {
      for (const tr of stream.getTracks()) tr.stop()
      return
    }
    camStream = stream
    video.srcObject = stream
    video.muted = true
    video.playsInline = true
    await video.play()
    await tracker.start(video)
    if (!camWanted) {
      stopCam()
      return
    }
    trackingUp = true
    const label = stream.getVideoTracks()[0]?.label || 'camera'
    console.log('[mingo] tracking started', label, `${video.videoWidth}x${video.videoHeight}`)
  } catch (err) {
    console.warn('[mingo] camera/tracking unavailable — idle mode', err)
  } finally {
    camBusy = false
  }
}

/** 트래커 + 카메라 완전 정지 (카메라 LED off) */
function stopCam() {
  trackingUp = false
  tracker.stop()
  if (camStream) {
    for (const tr of camStream.getTracks()) tr.stop()
    camStream = null
  }
  video.srcObject = null
  overlayCtx?.clearRect(0, 0, overlay?.width ?? 0, overlay?.height ?? 0)
}
startCam()

// ---------- 트래킹 패널 드래그 (윈도우 안 배치, 잘림 방지 클램프) ----------
let panelDragging = false
let panelUserMoved = false
let panelDragOrigin = { mx: 0, my: 0, left: 0, top: 0 }
/** 패널 위/드래그 중이면 클릭스루 끄기 */
let overTrackPanel = false

function clampPanelPos(left: number, top: number) {
  const pw = trackPanel?.offsetWidth ?? 360
  const ph = trackPanel?.offsetHeight ?? 270
  const maxL = Math.max(0, window.innerWidth - pw)
  const maxT = Math.max(0, window.innerHeight - ph)
  return {
    left: Math.min(maxL, Math.max(0, left)),
    top: Math.min(maxT, Math.max(0, top)),
  }
}

const PANEL_W = 220
const PANEL_H = 165
const HUD_GAP = 6
const EDGE = 8

/**
 * 기본: 창 왼쪽 아래 작은 오버레이 (전신과 최소 겹침).
 * 드래그로 이동 가능. 메뉴로 숨기기/크기 조절.
 */
function placePanelDefault() {
  if (!trackPanel) return
  applyPanelScale()
  trackPanel.style.display = showTrackPanel ? 'block' : 'none'
  if (hud) hud.style.display = showTrackHud ? 'block' : 'none'
  if (!showTrackPanel) {
    placeHudBesidePanel()
    return
  }
  const pw = trackPanel.offsetWidth || PANEL_W * panelScale
  const ph = trackPanel.offsetHeight || PANEL_H * panelScale
  const hudW = showTrackHud ? (hud?.offsetWidth || 160) : 0
  const left = EDGE + (showTrackHud ? hudW + HUD_GAP : 0)
  const top = Math.max(EDGE, window.innerHeight - ph - EDGE)
  const p = clampPanelPos(left, top)
  trackPanel.style.left = `${p.left}px`
  trackPanel.style.top = `${p.top}px`
  trackPanel.style.bottom = 'auto'
  trackPanel.style.right = 'auto'
  placeHudBesidePanel()
}

function applyPanelScale() {
  if (!trackPanel) return
  trackPanel.style.width = `${PANEL_W * panelScale}px`
  trackPanel.style.height = `${PANEL_H * panelScale}px`
}

function placeHudBesidePanel() {
  if (!hud) return
  hud.style.display = showTrackHud ? 'block' : 'none'
  if (!showTrackHud) return
  const ph = showTrackPanel
    ? (trackPanel?.offsetHeight || PANEL_H * panelScale)
    : 80
  const hudH = hud.offsetHeight || 90
  const top = Math.max(EDGE, window.innerHeight - ph - EDGE)
  let hudTop = top + Math.max(0, (ph - hudH) / 2)
  hudTop = Math.min(hudTop, window.innerHeight - hudH - EDGE)
  hud.style.left = `${EDGE}px`
  hud.style.top = `${hudTop}px`
  hud.style.bottom = 'auto'
  hud.style.right = 'auto'
}

let panelScale = 1.0

placePanelDefault()
// 레이아웃 안정화 후 HUD 너비 반영해 한 번 더
requestAnimationFrame(() => placePanelDefault())
window.addEventListener('resize', () => {
  if (!trackPanel || panelDragging) {
    placeHudBesidePanel()
    return
  }
  if (!panelUserMoved) {
    placePanelDefault()
  } else {
    const left = parseFloat(trackPanel.style.left || '0')
    const top = parseFloat(trackPanel.style.top || '0')
    const p = clampPanelPos(left, top)
    trackPanel.style.left = `${p.left}px`
    trackPanel.style.top = `${p.top}px`
    placeHudBesidePanel()
  }
})

if (trackPanel) {
  trackPanel.addEventListener('pointerenter', () => {
    overTrackPanel = true
    window.mingo?.setClickThrough(false)
  })
  trackPanel.addEventListener('pointerleave', () => {
    if (panelDragging) return
    overTrackPanel = false
  })
  trackPanel.addEventListener('pointerdown', (e) => {
    // 패널 드래그 (titlebar 또는 패널 전체)
    panelDragging = true
    panelUserMoved = true
    trackPanel.classList.add('dragging')
    overTrackPanel = true
    window.mingo?.setClickThrough(false)
    const rect = trackPanel.getBoundingClientRect()
    panelDragOrigin = {
      mx: e.clientX,
      my: e.clientY,
      left: rect.left,
      top: rect.top,
    }
    trackPanel.setPointerCapture(e.pointerId)
    e.preventDefault()
    e.stopPropagation()
  })
  trackPanel.addEventListener('pointermove', (e) => {
    if (!panelDragging) return
    const dx = e.clientX - panelDragOrigin.mx
    const dy = e.clientY - panelDragOrigin.my
    const p = clampPanelPos(panelDragOrigin.left + dx, panelDragOrigin.top + dy)
    trackPanel.style.left = `${p.left}px`
    trackPanel.style.top = `${p.top}px`
    placeHudBesidePanel()
    e.stopPropagation()
  })
  const endPanelDrag = (e: PointerEvent) => {
    if (!panelDragging) return
    panelDragging = false
    trackPanel.classList.remove('dragging')
    placeHudBesidePanel()
    try {
      trackPanel.releasePointerCapture(e.pointerId)
    } catch {
      /* ignore */
    }
    e.stopPropagation()
  }
  trackPanel.addEventListener('pointerup', endPanelDrag)
  trackPanel.addEventListener('pointercancel', endPanelDrag)
}

// ---------- 커서(전역) → 시선 + 히트테스트 + 드래그 ----------
let cursor: CursorInfo | null = null
let cursorInWindow = false
let cursorWin = { x: 0, y: 0 }

const clampUnit = (v: number) => Math.max(-1, Math.min(1, v))

window.mingo?.onCursor((p) => {
  // 계약(contract.ts CursorInfo): "아바타 기준" -1..1 — 윈도 중심에서 커서까지의
  // 오프셋을 화면 반폭/반높이로 감쇠 정규화 (화면 절대 좌표 기준이 아님).
  const dx = p.wx - p.winW / 2
  const dy = p.wy - p.winH / 2
  cursor = {
    nx: clampUnit(dx / (p.screenW / 2)),
    ny: clampUnit(dy / (p.screenH / 2)),
  }
  cursorInWindow = p.inWindow
  cursorWin = { x: p.wx, y: p.wy }
  // 히트테스트는 커서 데이터가 갱신될 때만 (≤30Hz), 위치 불변이면 skip
  if (p.wx !== lastHitWx || p.wy !== lastHitWy) {
    lastHitWx = p.wx
    lastHitWy = p.wy
    updateHitTest()
  }
})

// 드래그 우선: 창 안에서는 항상 클릭 수신 (클릭스루 OFF).
// 예전 레이캐스트 전용 방식은 전신 프레이밍이 어긋나면 드래그가 아예 안 됨.
let clickThrough = false
let lastHitWx = Number.NaN
let lastHitWy = Number.NaN
// 시작 즉시 드래그 가능
window.mingo?.setClickThrough(false)

function updateHitTest() {
  if (!window.mingo) return
  // 드래그/패널 조작 중엔 무조건 수신
  if (dragging || panelDragging || overTrackPanel) {
    if (clickThrough) {
      clickThrough = false
      window.mingo.setClickThrough(false)
    }
    return
  }
  // 창 안이면 클릭스루 OFF (어디든 드래그). 창 밖 커서만 통과.
  const wantThrough = !cursorInWindow
  if (wantThrough !== clickThrough) {
    clickThrough = wantThrough
    window.mingo.setClickThrough(wantThrough)
  }
}

// 아바타 드래그로 윈도우 이동 (패널 위 드래그는 위에서 처리)
let dragging = false
let lastDrag = { x: 0, y: 0 }
window.addEventListener('mousedown', (e) => {
  if (panelDragging || overTrackPanel) return
  if (trackPanel) {
    const r = trackPanel.getBoundingClientRect()
    if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) {
      return
    }
  }
  dragging = true
  lastDrag = { x: e.screenX, y: e.screenY }
})
window.addEventListener('mousemove', (e) => {
  if (!dragging || panelDragging) return
  // mouseup이 유실된 경우(클릭스루 전환 등) 버튼 상태로 드래그 종료 감지
  if (e.buttons === 0) {
    dragging = false
    return
  }
  window.mingo?.dragBy(e.screenX - lastDrag.x, e.screenY - lastDrag.y)
  lastDrag = { x: e.screenX, y: e.screenY }
})
window.addEventListener('mouseup', () => { dragging = false })
window.addEventListener('blur', () => { dragging = false })

// ---------- 메인 루프 ----------
// rAF는 디스플레이 주사율(ProMotion 120Hz)을 따르므로 시간 게이트로 프레임 캡:
// idle 30fps(데이터 소스가 30Hz + 모션 주기 3.6~11s라 시각 차이 없음),
// tracked 60fps(30Hz 트래킹의 스무딩 필터 보간용 상한).
const IDLE_FRAME_MS = 1000 / 30
const TRACKED_FRAME_MS = 1000 / 60
const clock = new THREE.Clock()
let rafId = 0
let lastRenderMs = 0
let lastTracked = 0
function loop() {
  rafId = requestAnimationFrame(loop)
  const nowMs = performance.now()
  const targetMs = lastTracked > 0.5 ? TRACKED_FRAME_MS : IDLE_FRAME_MS
  // -1ms 허용 오차: rAF 틱 양자화(8.33/16.7ms)로 캡이 한 틱씩 밀리는 것 방지
  if (nowMs - lastRenderMs < targetMs - 1) return
  lastRenderMs = nowMs

  const dt = Math.min(clock.getDelta(), 0.1)
  const t = clock.elapsedTime

  const raw = trackingUp ? tracker.latest() : neutralFrame()
  const frame = aliveness.compose(raw, dt, t, cursor)
  lastTracked = frame.tracked
  mingo.apply(frame, dt, t)

  // ---- 카메라 + 노드/엣지 디버그 패널 ----
  const dbg = window.__mingoTracking
  if (trackingUp && overlay && overlayCtx) {
    const dpr = window.devicePixelRatio || 1
    const cssW = trackPanel?.clientWidth || PANEL_W
    const cssH = trackPanel?.clientHeight || PANEL_H
    const rw = Math.max(1, Math.round(cssW * dpr))
    const rh = Math.max(1, Math.round(cssH * dpr))
    if (overlay.width !== rw || overlay.height !== rh) {
      overlay.width = rw
      overlay.height = rh
    }
    drawTrackingOverlay(overlayCtx, {
      w: overlay.width,
      h: overlay.height,
      video,
      face: dbg?.face ?? null,
      hands: dbg?.hands ?? [],
      pose: dbg?.pose ?? null,
      mirror: true,
    })
    if (hud && dbg && Math.floor(t * 4) !== Math.floor((t - dt) * 4)) {
      const pct = (v: number) => Math.round(v * 100)
      const vis = dbg.lastPoseVis
      hud.textContent = [
        `fps ${dbg.fps}  face ${dbg.faceSeen ? 'YES' : 'no'}  ${pct(dbg.tracked)}%`,
        `pose ${dbg.pose ? 'YES' : 'no'}  hands ${dbg.handCount}`,
        `cam ${dbg.camW}x${dbg.camH}`,
        vis
          ? `vis armL ${pct(vis.armL)} armR ${pct(vis.armR)} body ${pct(vis.body)}`
          : 'vis —',
        `mouth ${pct(frame.mouthOpen)} blink ${pct(Math.max(frame.blinkL, frame.blinkR))}`,
      ].join('\n')
      if (!panelUserMoved) placePanelDefault()
      else placeHudBesidePanel()
      if (panelBadge) {
        panelBadge.textContent = dbg.faceSeen
          ? `f${dbg.face?.length ?? 0} p${dbg.pose ? 33 : 0} h${dbg.handCount}`
          : 'no face'
      }
    }
  }

  renderer.render(scene, camera)
}
loop()

// ---------- 디버그 UI 메뉴 (크기/표시) ----------
function setTrackPanelVisible(on: boolean) {
  showTrackPanel = on
  panelUserMoved = false
  placePanelDefault()
  frameCamera()
}
function setTrackHudVisible(on: boolean) {
  showTrackHud = on
  placePanelDefault()
}
function setPanelScale(s: number) {
  panelScale = Math.min(1.6, Math.max(0.7, s))
  panelUserMoved = false
  applyPanelScale()
  placePanelDefault()
}
function setAvatarZoom(z: number) {
  avatarZoom = Math.min(1.6, Math.max(0.7, z))
  frameCamera()
}

// 우클릭 컨텍스트 메뉴 (패널/배경)
function openDebugMenu(clientX: number, clientY: number) {
  const existing = document.getElementById('debug-menu')
  existing?.remove()
  const menu = document.createElement('div')
  menu.id = 'debug-menu'
  menu.style.cssText = [
    'position:fixed',
    `left:${clientX}px`,
    `top:${clientY}px`,
    'z-index:100',
    'min-width:200px',
    'padding:6px 0',
    'border-radius:10px',
    'background:rgba(16,18,28,0.95)',
    'border:1px solid rgba(255,255,255,0.25)',
    'box-shadow:0 8px 24px rgba(0,0,0,0.45)',
    'color:#f4f7ff',
    'font:12px/1.4 ui-monospace,Menlo,monospace',
    'pointer-events:auto',
  ].join(';')
  const item = (label: string, fn: () => void) => {
    const b = document.createElement('button')
    b.type = 'button'
    b.textContent = label
    b.style.cssText =
      'display:block;width:100%;text-align:left;padding:8px 12px;border:0;background:transparent;color:inherit;cursor:pointer;font:inherit'
    b.onmouseenter = () => {
      b.style.background = 'rgba(94,200,255,0.18)'
    }
    b.onmouseleave = () => {
      b.style.background = 'transparent'
    }
    b.onclick = () => {
      fn()
      menu.remove()
    }
    menu.appendChild(b)
  }
  item(showTrackPanel ? '✓ 카메라 패널 숨기기' : '카메라 패널 보이기', () =>
    setTrackPanelVisible(!showTrackPanel),
  )
  item(showTrackHud ? '✓ 스펙 로그 숨기기' : '스펙 로그 보이기', () =>
    setTrackHudVisible(!showTrackHud),
  )
  item('패널 작게', () => setPanelScale(panelScale - 0.15))
  item('패널 크게', () => setPanelScale(panelScale + 0.15))
  item('패널 크기 리셋', () => setPanelScale(1))
  item('아바타 작게', () => setAvatarZoom(avatarZoom + 0.1))
  item('아바타 크게', () => setAvatarZoom(avatarZoom - 0.1))
  item('아바타 크기 리셋', () => setAvatarZoom(1))
  item('레이아웃 리셋 (발 밑)', () => {
    panelUserMoved = false
    panelScale = 1
    applyPanelScale()
    placePanelDefault()
  })
  const sep = document.createElement('div')
  sep.style.cssText = 'height:1px;margin:6px 10px;background:rgba(255,255,255,0.15)'
  menu.appendChild(sep)
  item('종료', () => {
    window.mingo?.quit()
  })
  document.body.appendChild(menu)
  window.mingo?.setClickThrough(false)
  const close = (ev: MouseEvent) => {
    if (!menu.contains(ev.target as Node)) {
      menu.remove()
      window.removeEventListener('mousedown', close, true)
    }
  }
  setTimeout(() => window.addEventListener('mousedown', close, true), 0)
}

window.addEventListener('contextmenu', (e) => {
  e.preventDefault()
  openDebugMenu(e.clientX, e.clientY)
})

// Electron 메뉴 / 단축키에서 호출
window.mingo?.onDebugCommand?.((cmd) => {
  if (cmd === 'toggle-panel') setTrackPanelVisible(!showTrackPanel)
  else if (cmd === 'toggle-hud') setTrackHudVisible(!showTrackHud)
  else if (cmd === 'panel-smaller') setPanelScale(panelScale - 0.15)
  else if (cmd === 'panel-larger') setPanelScale(panelScale + 0.15)
  else if (cmd === 'avatar-smaller') setAvatarZoom(avatarZoom + 0.1)
  else if (cmd === 'avatar-larger') setAvatarZoom(avatarZoom - 0.1)
  else if (cmd === 'reset-layout') {
    panelUserMoved = false
    panelScale = 1
    avatarZoom = 1
    applyPanelScale()
    placePanelDefault()
    frameCamera()
  } else if (cmd === 'quit') {
    window.mingo?.quit()
  }
})

// ---------- 가시성 연동 (Cmd+Shift+M 퀵 하이드) ----------
// backgroundThrottling:false라 hide 후에도 rAF가 계속 돌고, visibilityState도
// 'visible'로 남는다(Electron 문서화 동작) — main 프로세스가 방송하는
// mingo:visibility로 전체 파이프라인(루프+트래커+카메라 LED)을 멈추고 복귀 시 재시작.
let pipelinePaused = false
function setPipelineVisible(visible: boolean) {
  if (visible === !pipelinePaused) return // 중복 이벤트 무시 (idempotent)
  if (!visible) {
    pipelinePaused = true
    cancelAnimationFrame(rafId)
    camWanted = false
    stopCam()
  } else {
    pipelinePaused = false
    camWanted = true
    startCam()
    clock.getDelta() // 숨김 기간 델타 플러시 (복귀 프레임 점프 방지)
    cancelAnimationFrame(rafId) // 중복 루프 방지
    loop()
  }
}
window.mingo?.onVisibility?.((visible) => setPipelineVisible(visible))
// 브라우저 dev 실행 등 브리지 부재 환경 폴백
document.addEventListener('visibilitychange', () => setPipelineVisible(!document.hidden))
