// Value: protects=the "Nächste Sitzungswoche" line of puls.html shows the right state for the reader's own date in Europe/Berlin (frozen through a Date override): the build's fallback at the build date, the next week in a sitzungsfreie week, "läuft" inside a later Sitzungswoche, and a hidden line in the shown running week and past the list, with time elements and no script error; fails_when=the inline script throws at load, picks the wrong week, leaves the fallback in place, writes a wrong KW or gap sentence, or the browser's Intl date differs from the Python states table; why_new=Python render tests assert the fallback markup but cannot run the inline script or an injected reader date; seam=none; no_claim=browser engines other than Chrome/Chromium, other time zones than the reader's clock being frozen to one instant
(async function (expected) {
  const assert = (condition, message) => { if (!condition) throw new Error(`${expected.label}: ${message}`); };
  const text = (node) => node.textContent.replace(/\s+/g, ' ').trim();
  const line = document.querySelector('p.next-sitting');
  assert(line, 'the next-sitting line is missing');
  assert(document.querySelectorAll('p.next-sitting').length === 1, 'more than one next-sitting line');
  assert((window.__errors || []).length === 0, `script errors: ${(window.__errors || []).join('; ')}`);
  const slot = (name) => line.querySelector(`[data-next-sitting-${name}]`);
  assert(slot('lead') && slot('range') && slot('kw') && slot('gap'), 'a slot is missing');

  if (expected.fallback) {
    // Reader date == build date: the script must reproduce the server-rendered line.
    const nojs = new DOMParser().parseFromString(await (await fetch('next-sitting-nojs.html')).text(), 'text/html');
    const fallback = nojs.querySelector('p.next-sitting');
    assert(fallback, 'the no-script copy has no line');
    assert(text(line) === text(fallback), `text differs from the fallback: "${text(line)}" vs "${text(fallback)}"`);
    assert(line.hidden === fallback.hasAttribute('hidden'), 'hidden state differs from the fallback');
  } else if (expected.hidden) {
    assert(line.hidden === true, 'the line should be hidden');
    assert(getComputedStyle(line).display === 'none', 'the hidden line is still displayed');
  } else {
    assert(line.hidden === false, 'the line should be visible');
    assert(getComputedStyle(line).display !== 'none', 'the line is not displayed');
    assert(text(slot('lead')) === expected.lead, `lead is "${text(slot('lead'))}"`);
    assert(text(slot('range')) === expected.range, `range is "${text(slot('range'))}"`);
    assert(text(slot('kw')) === expected.kw, `kw is "${text(slot('kw'))}"`);
    if (expected.gap) assert(text(slot('gap')).includes(expected.gap), `gap is "${text(slot('gap'))}"`);
    else assert(text(slot('gap')) === '', `unexpected gap "${text(slot('gap'))}"`);
    const times = [...line.querySelectorAll('time')];
    assert(times.length === 2 && times.every((el) => /^\d{4}-\d{2}-\d{2}$/.test(el.getAttribute('datetime'))), 'dates are not in <time datetime> elements');
    assert(expected.datetimes.join() === times.map((el) => el.getAttribute('datetime')).join(), `datetimes are ${times.map((el) => el.getAttribute('datetime'))}`);
    assert(line.querySelector('a[href="https://www.bundestag.de/parlament/plenum/sitzungskalender"]'), 'the Sitzungskalender link is missing');
    assert(line.querySelectorAll('a').length === 1, 'more than one link in the line');
  }
  assert(line.getAttribute('data-sitzungswochen').length > 0, 'the embedded weeks were removed');
  return { label: expected.label, hidden: line.hidden, text: text(line) };
})
