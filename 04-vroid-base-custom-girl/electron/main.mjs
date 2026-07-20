// mingo-mate — macOS 데스크톱 마스코트 셸
// 리서치 검증된 레시피: transparent + frame:false + type:'panel' + screen-saver level
// + visibleOnFullScreen + setIgnoreMouseEvents(forward) + 렌더러 히트테스트 토글
import { app, BrowserWindow, ipcMain, screen, globalShortcut, session, Menu, systemPreferences } from 'electron'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const __dirname = dirname(fileURLToPath(import.meta.url))

// 아바타 + 하단 디버그 패널(360×270)이 잘리지 않게
const WIN_W = 520
const WIN_H = 780

/** @type {BrowserWindow | null} */
let win = null
let cursorTimer = null

function createWindow() {
  const { workArea } = screen.getPrimaryDisplay()
  // 화면 안에 완전히 들어오도록 배치
  const x = Math.min(
    workArea.x + workArea.width - WIN_W - 24,
    workArea.x + workArea.width - WIN_W,
  )
  const y = Math.min(
    workArea.y + workArea.height - WIN_H - 8,
    workArea.y + Math.max(0, workArea.height - WIN_H),
  )

  win = new BrowserWindow({
    width: WIN_W,
    height: WIN_H,
    x: Math.max(workArea.x, x),
    y: Math.max(workArea.y, y),
    transparent: true,
    frame: false,
    type: 'panel', // NSPanel: 풀스크린 앱 위에도 뜸 (electron#36364 회피)
    hasShadow: false,
    resizable: true,
    minWidth: 420,
    minHeight: 640,
    fullscreenable: false,
    webPreferences: {
      preload: join(__dirname, 'preload.cjs'),
      backgroundThrottling: false,
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  win.setAlwaysOnTop(true, 'screen-saver')
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })
  if (win.setHiddenInMissionControl) win.setHiddenInMissionControl(true)
  // 기본 클릭스루 OFF — 드래그/우클릭 종료 가능. 렌더러가 창 밖 커서일 때만 ON
  win.setIgnoreMouseEvents(false)

  const devServer = process.env.VITE_DEV_SERVER
  if (devServer) {
    // concurrently가 electron을 vite보다 먼저 띄울 수 있음 → 실패 시 재시도
    const url = `${devServer}/index.html`
    let attempts = 0
    const maxAttempts = 60
    const loadDev = () => {
      if (!win || win.isDestroyed()) return
      attempts += 1
      win.loadURL(url).catch(() => {
        /* did-fail-load 가 처리 */
      })
    }
    win.webContents.on('did-fail-load', (_e, code, desc, validatedURL) => {
      if (!devServer || !validatedURL?.startsWith(devServer)) return
      if (attempts >= maxAttempts) {
        console.error('[mingo] dev server never ready:', url, code, desc)
        return
      }
      console.log(`[mingo] wait vite… (${attempts}/${maxAttempts}) ${desc}`)
      setTimeout(loadDev, 250)
    })
    win.webContents.on('did-finish-load', () => {
      console.log('[mingo] renderer loaded', url)
    })
    loadDev()
  } else {
    win.loadFile(join(__dirname, '../dist/index.html'))
  }

  // backgroundThrottling:false면 hide 후에도 renderer의 visibilityState가 'visible'로
  // 남아 visibilitychange가 발화하지 않는다 (Electron 문서화 동작).
  // → hide/show를 명시적 IPC로 방송해 renderer가 렌더 루프·웹캠·MediaPipe를 멈추게 한다.
  win.on('hide', () => { if (win && !win.isDestroyed()) win.webContents.send('mingo:visibility', false) })
  win.on('show', () => { if (win && !win.isDestroyed()) win.webContents.send('mingo:visibility', true) })

  // 전역 커서 방송 (시선 추적 + 히트테스트용) — 30Hz
  cursorTimer = setInterval(() => {
    if (!win || win.isDestroyed() || !win.isVisible()) return
    const p = screen.getCursorScreenPoint()
    const b = win.getBounds()
    const d = screen.getPrimaryDisplay()
    win.webContents.send('mingo:cursor', {
      sx: p.x, sy: p.y,
      wx: p.x - b.x, wy: p.y - b.y,
      inWindow: p.x >= b.x && p.x < b.x + b.width && p.y >= b.y && p.y < b.y + b.height,
      winW: b.width, winH: b.height,
      screenW: d.size.width, screenH: d.size.height,
    })
  }, 33)
}

app.whenReady().then(async () => {
  // 카메라 권한 자동 허용 (macOS 시스템 프롬프트는 별도로 1회 뜸)
  session.defaultSession.setPermissionRequestHandler((_wc, permission, cb) => {
    cb(permission === 'media')
  })
  session.defaultSession.setPermissionCheckHandler((_wc, permission) => permission === 'media')

  // macOS TCC: getUserMedia 전에 메인 프로세스에서 카메라 권한 요청
  if (process.platform === 'darwin') {
    try {
      const status = systemPreferences.getMediaAccessStatus('camera')
      console.log('[mingo] camera TCC status:', status)
      if (status !== 'granted') {
        const ok = await systemPreferences.askForMediaAccess('camera')
        console.log('[mingo] askForMediaAccess(camera) →', ok)
      }
    } catch (err) {
      console.warn('[mingo] camera permission probe failed', err)
    }
  }

  const sendDebug = (cmd) => {
    if (win && !win.isDestroyed()) win.webContents.send('mingo:debug-cmd', cmd)
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: 'MingoMate',
      submenu: [
        { label: 'Mingo 숨기기/보이기', accelerator: 'Cmd+Shift+M', click: () => { if (win) win.isVisible() ? win.hide() : win.show() } },
        { role: 'reload' },
        { role: 'toggleDevTools' }, // 주의: 투명창은 detached 모드로만
        { type: 'separator' },
        { label: 'MingoMate 종료', accelerator: 'Cmd+Q', click: () => app.quit() },
      ],
    },
    {
      label: '보기',
      submenu: [
        { label: '카메라 패널 토글', accelerator: 'Cmd+Shift+P', click: () => sendDebug('toggle-panel') },
        { label: '스펙 로그 토글', accelerator: 'Cmd+Shift+L', click: () => sendDebug('toggle-hud') },
        { type: 'separator' },
        { label: '패널 작게', accelerator: 'Cmd+-', click: () => sendDebug('panel-smaller') },
        { label: '패널 크게', accelerator: 'Cmd+=', click: () => sendDebug('panel-larger') },
        { type: 'separator' },
        { label: '아바타 작게', accelerator: 'Cmd+Shift+-', click: () => sendDebug('avatar-smaller') },
        { label: '아바타 크게', accelerator: 'Cmd+Shift+=', click: () => sendDebug('avatar-larger') },
        { type: 'separator' },
        { label: '레이아웃 리셋 (발 밑)', accelerator: 'Cmd+Shift+0', click: () => sendDebug('reset-layout') },
        { type: 'separator' },
        { label: '종료', accelerator: 'Cmd+Shift+Q', click: () => app.quit() },
      ],
    },
  ]))

  createWindow()
  if (win && !win.isDestroyed()) {
    win.show()
    win.focus()
  }

  // 방송 화면공유 대비 퀵 하이드 (setContentProtection은 macOS 15+에서 무력)
  globalShortcut.register('CommandOrControl+Shift+M', () => {
    if (win) win.isVisible() ? win.hide() : win.show()
  })
})

ipcMain.on('mingo:click-through', (_e, enabled) => {
  if (!win) return
  win.setIgnoreMouseEvents(!!enabled, { forward: true })
})

ipcMain.on('mingo:drag-by', (_e, dx, dy) => {
  if (!win) return
  const b = win.getBounds()
  win.setBounds({ ...b, x: Math.round(b.x + dx), y: Math.round(b.y + dy) })
})

ipcMain.on('mingo:quit', () => app.quit())

app.on('will-quit', () => {
  if (cursorTimer) clearInterval(cursorTimer)
  globalShortcut.unregisterAll()
})

app.on('window-all-closed', () => app.quit())
