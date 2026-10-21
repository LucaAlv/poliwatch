// Controlled clipboard promises exercise the actual emitted runtime in fresh frames.
(async function () {
  const assert = (ok, message) => { if (!ok) throw new Error(message); };
  const fixture = await (await fetch('/recipes.html')).text();
  const fallbackLabel = 'Markiert – mit ⌘C/Strg+C kopieren';
  function setup(unavailable) {
    window.writes = [];
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: unavailable ? undefined : {
      writeText(text) { return new Promise((resolve, reject) => writes.push({ text, resolve, reject })); },
    } });
    window.timers = new Map();
    let timerId = 0;
    window.setTimeout = (fn, ms) => { timers.set(++timerId, { fn, ms }); return timerId; };
    window.clearTimeout = id => timers.delete(id);
  }
  let passed = 0;
  async function scenario(name, run, unavailable = false) {
    const frame = document.createElement('iframe');
    frame.srcdoc = `<script>(${setup})(${unavailable})<\/script>` + fixture;
    const loaded = new Promise(resolve => { frame.onload = resolve; });
    document.body.append(frame);
    await loaded;
    const w = frame.contentWindow, d = w.document;
    const buttons = [...d.querySelectorAll('button')], codes = [...d.querySelectorAll('code')];
    const selection = w.getSelection();
    const range = (index, start = 0, end = 6) => {
      const r = d.createRange(); r.setStart(codes[index].firstChild, start); r.setEnd(codes[index].firstChild, end); return r;
    };
    const select = (index, start = 0, end = 6) => {
      selection.removeAllRanges(); selection.addRange(range(index, start, end));
    };
    const endpoints = (s = w.getSelection()) => Array.from({ length: s?.rangeCount || 0 }, (_, i) => {
      const r = s.getRangeAt(i); return [r.startContainer, r.startOffset, r.endContainer, r.endOffset];
    });
    const same = expected => {
      const actual = endpoints();
      return actual.length === expected.length && actual.every((r, i) => r.every((v, j) => v === expected[i][j]));
    };
    const settle = async (index = 0, success = false) => {
      assert(w.writes[index]?.text === codes[index === 1 ? 1 : 0].textContent, name + ': clipboard payload');
      w.writes[index][success ? 'resolve' : 'reject'](); await Promise.resolve();
    };
    const fallback = (index = 0) => {
      const r = w.getSelection()?.getRangeAt(0);
      assert(r?.startContainer === codes[index] && r.startOffset === 0 &&
        r.endContainer === codes[index] && r.endOffset === codes[index].childNodes.length,
      name + ': fallback endpoints');
      assert(buttons[index].textContent === fallbackLabel, name + ': fallback feedback');
    };
    try {
      assert(buttons.every(b => !b.hidden), name + ': buttons wired');
      await run({ w, buttons, codes, selection, range, select, endpoints, same, settle, fallback });
      passed++;
    } finally { frame.remove(); }
  }
  for (const [name, move] of [
    ['equal text in another recipe', t => t.select(1)],
    ['equal text at another offset', t => t.select(0, 10, 16)],
    ['different text', t => t.select(1, 7, 9)],
    ['changed range count', t => t.selection.removeAllRanges()],
    ['moved collapsed caret', t => t.select(0, 2, 2)],
  ]) {
    await scenario(name, async t => {
      t.select(0, 0, name === 'moved collapsed caret' ? 0 : 6);
      const before = t.endpoints(), text = String(t.selection);
      t.buttons[0].click(); move(t);
      const after = t.endpoints();
      assert(!t.same(before), name + ': endpoints must change');
      if (name.startsWith('equal text')) assert(String(t.selection) === text, name + ': equal-text precondition');
      await t.settle();
      assert(t.same(after), name + ': rejected write replaced the reader selection');
      assert(t.buttons[0].textContent === 'Nicht kopiert', name + ': failure feedback');
    });
  }
  for (const state of ['unchanged range', 'unchanged empty', 'returned endpoints', 'unchanged caret']) {
    await scenario(state, async t => {
      if (state !== 'unchanged empty') t.select(0, 0, state === 'unchanged caret' ? 0 : 6);
      t.buttons[0].click();
      if (state === 'returned endpoints') { t.select(1); t.select(0); }
      await t.settle(); t.fallback();
    });
  }
  await scenario('null selection', async t => {
    const native = t.w.getSelection;
    t.w.getSelection = () => null;
    try { t.buttons[0].click(); await t.settle(); }
    finally { t.w.getSelection = native; }
    assert(t.buttons[0].textContent === fallbackLabel, 'null selection must behave as zero ranges');
  });
  for (const mutate of [false, true]) {
    await scenario('two ranges ' + mutate, async t => {
      const ranges = [t.range(0), t.range(1)];
      const native = t.w.getSelection;
      let fallbackCalls = 0;
      const substitute = {
        rangeCount: 2,
        getRangeAt(i) { assert(i < this.rangeCount, 'range access out of bounds'); return ranges[i]; },
        removeAllRanges() { fallbackCalls++; ranges.length = 0; this.rangeCount = 0; },
        addRange(r) { ranges.push(r); this.rangeCount = ranges.length; },
        toString() { return ranges.map(String).join(''); },
      };
      t.w.getSelection = () => substitute;
      try {
        t.buttons[0].click();
        if (mutate) { ranges[1].setStart(t.codes[1].firstChild, 10); ranges[1].setEnd(t.codes[1].firstChild, 16); }
        assert(t.w.getSelection().rangeCount === 2, 'multi-range precondition');
        const expected = t.endpoints();
        await t.settle();
        if (mutate) {
          assert(t.same(expected) && fallbackCalls === 0, 'second-range mutation must be preserved');
          assert(t.buttons[0].textContent === 'Nicht kopiert', 'second-range failure feedback');
        } else { t.fallback(); assert(fallbackCalls === 1, 'unchanged two ranges must permit fallback'); }
      } finally { t.w.getSelection = native; }
    });
  }
  for (const oldSuccess of [false, true]) {
    await scenario('stale settlement ' + oldSuccess, async t => {
      t.select(0); t.buttons[0].click(); t.buttons[1].click();
      await t.settle(1, true);
      const expected = t.endpoints();
      await t.settle(0, oldSuccess);
      assert(t.same(expected) && t.buttons[0].textContent === 'Kopieren' &&
        t.buttons[1].textContent === 'Kopiert', 'stale attempt changed selection or feedback');
    });
  }
  await scenario('feedback timers', async t => {
    t.buttons[0].click(); await t.settle(0, true);
    assert(t.buttons[0].textContent === 'Kopiert', 'latest success feedback');
    const oldTimer = [...t.w.timers.keys()][0];
    t.buttons[0].click();
    t.w.writes[1].reject(); await Promise.resolve(); t.fallback();
    assert(!t.w.timers.has(oldTimer) && t.w.timers.size === 1, 'new feedback must clear previous timer');
    const timer = [...t.w.timers.values()][0];
    assert(timer.ms === 2000, 'feedback reset duration');
    timer.fn(); assert(t.buttons[0].textContent === 'Kopieren', 'feedback must reset');
  });
  await scenario('clipboard unavailable', async t => {
    t.buttons[0].click(); t.fallback();
    assert(t.w.writes.length === 0, 'unavailable clipboard must fall back immediately');
  }, true);
  return { scenarios: passed };
})
