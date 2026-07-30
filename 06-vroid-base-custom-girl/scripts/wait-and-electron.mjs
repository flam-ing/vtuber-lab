// Wait until Vite is up, then start Electron (avoids ERR_CONNECTION_REFUSED race).
import { spawn } from 'node:child_process'
import { createRequire } from 'node:module'
import { setTimeout as sleep } from 'node:timers/promises'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)
const __dirname = dirname(fileURLToPath(import.meta.url))
const root = join(__dirname, '..')

// `electron` package exports the binary path when required from Node
const electronBin = require('electron')

const url = (process.env.VITE_DEV_SERVER || 'http://localhost:5183').replace(/\/$/, '')
const target = `${url}/index.html`

async function ready(timeoutMs = 45000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(target, { method: 'GET' })
      if (res.ok || res.status === 304) return true
    } catch {
      /* not up yet */
    }
    await sleep(200)
  }
  return false
}

const ok = await ready()
if (!ok) {
  console.error('[mingo] Vite not ready:', target)
  process.exit(1)
}
console.log('[mingo] Vite ready → launching Electron', electronBin)

const child = spawn(electronBin, ['.'], {
  cwd: root,
  stdio: 'inherit',
  env: {
    ...process.env,
    VITE_DEV_SERVER: url,
    ELECTRON_ENABLE_LOGGING: '1',
  },
})

child.on('error', (err) => {
  console.error('[mingo] failed to spawn electron', err)
  process.exit(1)
})
child.on('exit', (code, signal) => {
  console.log('[mingo] electron exit', { code, signal })
  process.exit(code ?? (signal ? 1 : 0))
})
