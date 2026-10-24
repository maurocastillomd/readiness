// Render scene.html to an MP4 by seeking the deterministic timeline frame by
// frame with puppeteer, then stitching with ffmpeg. Uses the toolchain in
// ~/html-to-mp4/node_modules.
const path = require('path');
const fs = require('fs');
const { execFileSync } = require('child_process');

const MODS = '/Users/maurocastillo/html-to-mp4/node_modules';
const puppeteer = require(path.join(MODS, 'puppeteer'));

const FPS = 30;
const W = 1920, H = 1080;
const OUT_DIR = path.join(__dirname, 'frames');
const SCENE = 'file://' + path.join(__dirname, 'scene.html');
const MP4 = path.join(__dirname, 'readiness-demo.mp4');

(async () => {
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--force-device-scale-factor=1', '--hide-scrollbars'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
  await page.evaluateOnNewDocument(() => { window.__RENDER__ = true; });
  await page.goto(SCENE, { waitUntil: 'networkidle0' });
  await page.evaluate(() => document.fonts.ready);

  const duration = await page.evaluate(() => window.DURATION);
  const hold = 1400; // freeze on the final frame
  const total = duration + hold;
  const frames = Math.ceil((total / 1000) * FPS);

  for (let i = 0; i < frames; i++) {
    const ms = Math.min((i / FPS) * 1000, duration);
    await page.evaluate((t) => window.seek(t), ms);
    await page.screenshot({
      path: path.join(OUT_DIR, `f${String(i).padStart(5, '0')}.png`),
      clip: { x: 0, y: 0, width: W, height: H },
    });
  }
  await browser.close();
  console.log(`captured ${frames} frames`);

  execFileSync('ffmpeg', [
    '-y', '-framerate', String(FPS),
    '-i', path.join(OUT_DIR, 'f%05d.png'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart', '-crf', '16', '-preset', 'slow',
    MP4,
  ], { stdio: 'inherit' });

  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  console.log('wrote ' + MP4);
})();
