import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const { spawn, spawnSync } = require('node:child_process');
const { setTimeout: delay } = require('node:timers/promises');
const { once } = require('node:events');
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const root = path.resolve(__dirname, '..');
const check = fs.readFileSync(path.join(__dirname, 'bills_browser_check.js'), 'utf8');
const recipeCheck = fs.readFileSync(path.join(__dirname, 'recipe_copy_browser_check.js'), 'utf8');
const weekCheck = fs.readFileSync(path.join(__dirname, 'week_comparison_browser_check.js'), 'utf8');
const chrome = process.env.CHROME_BIN || ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium', '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser'].find(fs.existsSync);
if (!chrome || !fs.existsSync(chrome)) throw new Error('Chrome/Chromium not found; install Chromium or set CHROME_BIN to its executable path');
if (typeof WebSocket !== 'function') throw new Error('Node 21+ with native WebSocket is required');

const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'bills-browser-'));
let browser, server, ws;
const waitFor = async (fn, ms = 15000) => {
  const end = Date.now() + ms;
  while (Date.now() < end) { const value = await fn(); if (value) return value; await delay(100); }
  throw new Error('Timed out waiting for Chrome DevTools');
};
function connect(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url), pending = new Map(), listeners = new Map();
    const timer = setTimeout(() => { socket.close(); reject(new Error('Chrome DevTools connection timed out')); }, 10000);
    let id = 0;
    socket.onmessage = event => {
      const msg = JSON.parse(event.data);
      if (!msg.id) { for (const listener of listeners.get(msg.method) || []) listener(msg.params); return; }
      const item = pending.get(msg.id);
      if (!item) return;
      pending.delete(msg.id);
      msg.error ? item.reject(new Error(JSON.stringify(msg.error))) : item.resolve(msg.result || {});
    };
    socket.onerror = () => { clearTimeout(timer); reject(new Error('Chrome DevTools WebSocket failed')); };
    socket.onclose = () => {
      clearTimeout(timer);
      const error = new Error('Chrome DevTools connection closed');
      reject(error);
      for (const item of pending.values()) item.reject(error);
      pending.clear();
    };
    socket.onopen = () => { clearTimeout(timer); resolve({
      waitEvent(method) {
        return new Promise((res, rej) => {
          const timer = setTimeout(() => rej(new Error(`Timed out waiting for ${method}`)), 10000);
          const listener = value => { clearTimeout(timer); listeners.set(method, listeners.get(method).filter(fn => fn !== listener)); res(value); };
          listeners.set(method, [...(listeners.get(method) || []), listener]);
        });
      },
      call(method, params = {}) {
        return new Promise((res, rej) => {
          const callId = ++id;
          const timer = setTimeout(() => { pending.delete(callId); rej(new Error(`Timed out waiting for ${method}`)); }, 10000);
          pending.set(callId, { resolve: value => { clearTimeout(timer); res(value); }, reject: error => { clearTimeout(timer); rej(error); } });
          socket.send(JSON.stringify({ id: callId, method, params }));
        });
      },
      async evaluate(expression) {
        const out = await this.call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
        if (out.exceptionDetails) throw new Error(out.exceptionDetails.exception?.description || out.exceptionDetails.text || 'browser assertion failed');
        const remote = out.result;
        if (remote.subtype === 'error') throw new Error(remote.description || 'browser assertion failed');
        return remote.value;
      }, close() { socket.close(); },
    }); };
  });
}
async function main() {
  const py = process.argv[2] || process.env.PYTHON || process.env.PYTHON3 || 'python3';
  const publicDir = path.join(temp, 'public'); fs.mkdirSync(publicDir);
  const fixture = spawnSync(py, [path.join(__dirname, 'test_bills.py'), '--browser-fixture', path.join(publicDir, 'site')], { cwd: root, encoding: 'utf8', timeout: 30000 });
  if (fixture.status !== 0) throw new Error(`fixture generation failed (${py}): ${fixture.error?.message || fixture.stderr || fixture.stdout}`);
  const recipeFixture = spawnSync(py, [path.join(__dirname, 'test_daten_page.py'), '--browser-fixture', path.join(publicDir, 'recipes.html')], { cwd: root, encoding: 'utf8', timeout: 30000 });
  if (recipeFixture.status !== 0) throw new Error(`recipe fixture generation failed (${py}): ${recipeFixture.error?.message || recipeFixture.stderr || recipeFixture.stdout}`);
  const weekFixture = spawnSync(py, [path.join(__dirname, 'test_build_dip_pulse_site.py'), '--browser-fixture', path.join(publicDir, 'weeks')], { cwd: root, encoding: 'utf8', timeout: 30000 });
  if (weekFixture.status !== 0) throw new Error(`week fixture generation failed (${py}): ${weekFixture.error?.message || weekFixture.stderr || weekFixture.stdout}`);
  server = http.createServer((req, res) => {
    let file = path.resolve(publicDir, '.' + decodeURIComponent(new URL(req.url, 'http://local').pathname));
    if (!file.startsWith(publicDir + path.sep)) { res.writeHead(403).end(); return; }
    fs.readFile(file, (err, body) => { if (err) { res.writeHead(404).end(); return; }
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' }); res.end(body); });
  });
  server.listen(0, '127.0.0.1'); await once(server, 'listening');
  const profile = path.join(temp, 'profile');
  browser = spawn(chrome, ['--headless=new', '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });
  await once(browser, 'spawn');
  const portFile = path.join(profile, 'DevToolsActivePort');
  await waitFor(() => fs.existsSync(portFile) && fs.readFileSync(portFile, 'utf8').split('\n')[0]);
  const port = fs.readFileSync(portFile, 'utf8').split('\n')[0];
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`, { signal: AbortSignal.timeout(10000) })).json();
  ws = await connect(targets.find(x => x.type === 'page').webSocketDebuggerUrl);
  await ws.call('Page.enable'); await ws.call('Runtime.enable'); await ws.call('Page.bringToFront'); await ws.call('Emulation.setFocusEmulationEnabled', { enabled: true });
  const origin = `http://127.0.0.1:${server.address().port}`;
  const recipesLoaded = ws.waitEvent('Page.loadEventFired');
  await ws.call('Page.navigate', { url: origin + '/recipes.html' }); await recipesLoaded;
  console.log(`PASS recipe copy: ${JSON.stringify(await ws.evaluate(`(${recipeCheck})()`))}`);
  for (const [label, width, height] of [['desktop', 1440, 1000], ['tablet', 700, 1000], ['mobile', 375, 844]]) {
    await ws.call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 });
    const loaded = ws.waitEvent('Page.loadEventFired');
    await ws.call('Page.navigate', { url: origin + '/weeks/current-only.html' }); await loaded;
    const result = await ws.evaluate(`(${weekCheck})()`);
    if (result.columns !== (width <= 460 ? 2 : 3) || result.noOverflow !== true) throw new Error(`${label} current-only layout failed: ${JSON.stringify(result)}`);
    console.log(`PASS ${label} current-only week: ${JSON.stringify(result)}`);
  }
  await ws.call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  const weekComparisonLoaded = ws.waitEvent('Page.loadEventFired');
  await ws.call('Page.navigate', { url: origin + '/weeks/comparison.html' }); await weekComparisonLoaded;
  console.log(`PASS ordinary week comparison: ${JSON.stringify(await ws.evaluate(`(${weekCheck})()`))}`);
  for (const [label, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
    await ws.call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 600 });
    for (const [name, file] of [['overview', '/site/index.html'], ['detail', '/site/detail.html'], ['protocol', '/protocols/plenarprotokoll-21-1.html#speech-4-ID0']]) {
      const loaded = ws.waitEvent('Page.loadEventFired'); await ws.call('Page.navigate', { url: origin + file }); await loaded;
      const expression = `(${check})()`;
      let result = await ws.evaluate(expression);
      if (name === 'overview') {
        const initialQuery = 'FU\u0308R';
        const loadedInitial = ws.waitEvent('Page.loadEventFired');
        await ws.call('Page.navigate', { url: origin + '/site/index.html?q=' + encodeURIComponent(initialQuery) }); await loadedInitial;
        const initialResult = await ws.evaluate(`(${check})({ initial: true })`);
        console.log(`PASS ${label} overview initial folded query/history: ${JSON.stringify(initialResult)}`);
      }
      if (name === 'protocol') {
        if (result.keyboardEnter !== 'pending on focused Repeat speech link') throw new Error(`${label} protocol missed keyboard setup: ${JSON.stringify(result)}`);
        await ws.call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
        await ws.call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 });
        await waitFor(() => ws.evaluate('document.getElementById("speech-4-ID0").open'));
        result = await ws.evaluate(expression);
        if (result.keyboardEnter !== 'passed') throw new Error(`${label} keyboard Enter failed: ${JSON.stringify(result)}`);
      }
      console.log(`PASS ${label} ${name}: ${JSON.stringify(result)}`);
    }
  }
}
main().catch(error => { console.error(`FAIL bills browser check: ${error.stack || error}`); process.exitCode = 1; }).finally(async () => {
  ws?.close(); server?.close();
  if (browser?.pid && browser.exitCode === null && browser.signalCode === null) {
    browser.kill('SIGTERM');
    await Promise.race([once(browser, 'exit'), delay(2000)]);
    if (browser.exitCode === null && browser.signalCode === null) { browser.kill('SIGKILL'); await once(browser, 'exit'); }
  }
  fs.rmSync(temp, { recursive: true, force: true });
});
