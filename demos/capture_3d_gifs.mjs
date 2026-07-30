#!/usr/bin/env node
/**
 * Capture rotating 3D slot demos (03 OBJ, 04 FBX, 05 VRM) via headless Chrome.
 * Requires: Chrome, ffmpeg, repo served at localhost:8799
 *
 *   node demos/capture_3d_gifs.mjs
 */
import { spawn, execFileSync } from 'node:child_process';
import { mkdirSync, rmSync, existsSync, writeFileSync, readFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const CHROME =
  process.env.CHROME ||
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const PORT = process.env.PORT || '8799';
const SIZE = 520;
const FPS = 12;
const SECONDS = 4.5;
const FRAMES = Math.round(FPS * SECONDS);

const JOBS = [
  { id: '03', m: 'obj', gif: '03-obj.gif', preview: '03-preview.jpg', slotPreview: join(ROOT, '03-flamingo-3d-obj', 'preview.png') },
  { id: '04', m: 'fbx', gif: '04-meshy.gif', preview: '04-preview.jpg', slotPreview: join(ROOT, '04-meshy-flamingo-fbx', 'preview.png') },
  { id: '05', m: 'vrm', gif: '05-vrm.gif', preview: '05-preview.jpg', slotPreview: join(ROOT, '05-flamingo-motion-vrm', 'preview.png') },
];

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function run(cmd, args, opts = {}) {
  return execFileSync(cmd, args, { stdio: 'inherit', ...opts });
}

async function waitReady(url, timeoutMs = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {}
    await sleep(200);
  }
  throw new Error('server not ready: ' + url);
}

async function main() {
  // ensure server
  let server;
  try {
    await fetch(`http://127.0.0.1:${PORT}/demos/view3d/capture.html`);
  } catch {
    server = spawn('python3', ['-m', 'http.server', PORT], {
      cwd: ROOT,
      stdio: 'ignore',
      detached: true,
    });
    server.unref();
    await waitReady(`http://127.0.0.1:${PORT}/README.md`);
  }

  const require = createRequire(import.meta.url);
  let puppeteer;
  try {
    puppeteer = require('puppeteer-core');
  } catch {
    console.log('installing puppeteer-core in /tmp…');
    run('npm', ['install', '--prefix', '/tmp/vtuber-capture', 'puppeteer-core@24'], {
      cwd: '/tmp',
    });
    puppeteer = createRequire('/tmp/vtuber-capture/package.json')('puppeteer-core');
  }

  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--use-angle=metal',
      '--enable-webgl',
      '--ignore-gpu-blocklist',
      `--window-size=${SIZE},${SIZE}`,
    ],
    defaultViewport: { width: SIZE, height: SIZE, deviceScaleFactor: 1 },
  });

  for (const job of JOBS) {
    const dir = join(__dirname, `_frames_${job.id}`);
    rmSync(dir, { recursive: true, force: true });
    mkdirSync(dir, { recursive: true });

    const url = `http://127.0.0.1:${PORT}/demos/view3d/capture.html?m=${job.m}&size=${SIZE}`;
    console.log(`\n=== ${job.id} ${job.m} ===\n${url}`);
    const page = await browser.newPage();
    page.on('console', (msg) => console.log('  [page]', msg.text()));
    page.on('pageerror', (e) => console.error('  [err]', e.message));

    await page.goto(url, { waitUntil: 'networkidle0', timeout: 120000 });
    await page.waitForFunction(() => window.__captureReady === true, { timeout: 120000 });
    await sleep(400);

    const interval = 1000 / FPS;
    for (let i = 0; i < FRAMES; i++) {
      const path = join(dir, `f${String(i).padStart(3, '0')}.png`);
      await page.screenshot({ path, type: 'png' });
      if (i === 0) {
        // still preview for demos/
        const prev = join(__dirname, job.preview);
        run('sips', ['-s', 'format', 'jpeg', '-s', 'formatOptions', '85', path, '--out', prev]);
        // also write slot preview if missing/overwrite for 05
        if (job.m === 'vrm' || !existsSync(job.slotPreview)) {
          run('sips', ['-z', '1024', '1024', path, '--out', job.slotPreview.replace(/\.png$/, '_cap.png')]);
          // keep existing high-res Meshy/OBJ previews; for VRM copy
          if (job.m === 'vrm') {
            run('cp', [path, job.slotPreview]);
          }
        }
      }
      process.stdout.write(`\r  frame ${i + 1}/${FRAMES}`);
      await sleep(interval);
    }
    process.stdout.write('\n');
    await page.close();

    const gifOut = join(__dirname, job.gif);
    // palette gif
    const pal = join(dir, 'pal.png');
    run('ffmpeg', [
      '-y', '-framerate', String(FPS),
      '-i', join(dir, 'f%03d.png'),
      '-vf', 'fps=12,scale=480:-1:flags=lanczos,palettegen=stats_mode=diff',
      pal,
    ]);
    run('ffmpeg', [
      '-y', '-framerate', String(FPS),
      '-i', join(dir, 'f%03d.png'),
      '-i', pal,
      '-lavfi', 'fps=12,scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=4',
      '-loop', '0',
      gifOut,
    ]);
    console.log('wrote', gifOut);

    // light cleanup of frames (keep disk sane)
    rmSync(dir, { recursive: true, force: true });
  }

  await browser.close();
  // leave server alone if we didn't start it
  if (server) {
    try { process.kill(-server.pid, 'SIGTERM'); } catch {}
  }
  console.log('\nall done');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
