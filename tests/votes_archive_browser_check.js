// Value: protects=the votes archive's inline chip filter (Fraktion and Politikfeld chips, OR within a group, AND across groups, the "x von y" count, the empty note, the month headings and the ?politikfeld= preload) works in a real browser, including the inverted "für den Antrag" path; fails_when=the inline script throws at load, a chip stops filtering, a month heading stays up with no row under it, or the preload keeps an unknown name; why_new=only a hand-run probe (2026-10-09) covered the script, Python tests assert markup but cannot run it; seam=none; no_claim=browser engines other than Chrome/Chromium
// Rows (tests/votes_archive_browser_fixture.py), in page order: 1 SPD yes, Verkehr (Mai); 2 CDU/CSU yes, Gesundheit (Mai);
// 3 inverted, SPD "für den Antrag", Verkehr + Gesundheit (April); 4 SPD tie, CDU/CSU yes, untagged (April).
(async function (opts) {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const options = opts || {};
  const container = document.querySelector('[data-archive]');
  assert(container, 'archive list is missing');
  const rows = [...container.querySelectorAll('[data-row]')];
  assert(rows.length === 4, `expected 4 archive rows, got ${rows.length}`);
  const headings = [...container.querySelectorAll('h2[data-month]')];
  assert(headings.length === 2, `expected 2 month headings, got ${headings.length}`);
  const [mai, april] = headings;
  const chip = (kind, name) => document.querySelector(`[data-${kind}-chip="${name}"]`);
  const spd = chip('fraktion', 'SPD'), cdu = chip('fraktion', 'CDU/CSU');
  const verkehr = chip('politikfeld', 'Verkehr'), gesundheit = chip('politikfeld', 'Gesundheit'), untagged = chip('politikfeld', 'untagged');
  assert(spd && cdu && verkehr && gesundheit && untagged, 'filter chips are missing');
  const empty = document.querySelector('[data-no-results]');
  const count = document.querySelector('[data-archive-count]');
  assert(empty && count, 'the empty note or the count is missing');
  // What the reader sees, not the hidden attribute: a stylesheet rule could undo [hidden].
  const shown = (element) => getComputedStyle(element).display !== 'none';
  const visibleRows = () => rows.map(shown);
  const countText = () => count.textContent.replace(/\s+/g, ' ').trim();
  const pressed = (element) => element.getAttribute('aria-pressed') === 'true' && element.classList.contains('is-active');
  const unpressed = (element) => element.getAttribute('aria-pressed') === 'false' && !element.classList.contains('is-active');
  const expectRows = (expected, step) => {
    const now = visibleRows();
    assert(JSON.stringify(now) === JSON.stringify(expected), `${step}: rows shown ${JSON.stringify(now)}, expected ${JSON.stringify(expected)}`);
  };
  const expectCount = (text, step) => assert(countText() === text, `${step}: count reads "${countText()}", expected "${text}"`);
  assert(document.documentElement.scrollWidth <= window.innerWidth, `horizontal overflow: ${document.documentElement.scrollWidth} > ${window.innerWidth}`);

  if (options.preload) {
    // ?politikfeld=Verkehr&politikfeld=Nichtda: the known name is pressed on load, the unknown one ignored.
    assert(pressed(verkehr) && unpressed(gesundheit) && unpressed(untagged), 'preload: only the Verkehr chip should be pressed');
    expectRows([true, false, true, false], 'preload');
    expectCount('2 von 4 Abstimmungen', 'preload');
    assert(!shown(empty), 'preload: the empty note shows although rows match');
    return { rows: rows.length, preloaded: 'Verkehr' };
  }

  // 1. Initial state.
  assert([spd, cdu, verkehr, gesundheit, untagged].every(unpressed), 'a chip is pressed before any click');
  expectRows([true, true, true, true], 'initial');
  assert(shown(mai) && shown(april), 'initial: a month heading is hidden');
  expectCount('4 Abstimmungen', 'initial');
  assert(!shown(empty), 'initial: the empty note shows');

  // 2. One Fraktion: rows 1 and 3 (row 3 through the inverted "für den Antrag" path).
  spd.click();
  expectRows([true, false, true, false], 'SPD');
  expectCount('2 von 4 Abstimmungen', 'SPD');
  assert(pressed(spd) && unpressed(cdu), 'SPD: chip state wrong');

  // 3. OR within a group: SPD or CDU/CSU shows all four (row 4 only through CDU/CSU, SPD is tied there).
  cdu.click();
  expectRows([true, true, true, true], 'SPD + CDU/CSU');
  expectCount('4 von 4 Abstimmungen', 'SPD + CDU/CSU');
  assert(pressed(cdu), 'SPD + CDU/CSU: chip state wrong');
  spd.click();
  expectRows([false, true, false, true], 'CDU/CSU');
  expectCount('2 von 4 Abstimmungen', 'CDU/CSU');

  // 4. AND across groups: CDU/CSU (rows 2, 4) and Verkehr (rows 1, 3) share no row.
  verkehr.click();
  expectRows([false, false, false, false], 'CDU/CSU + Verkehr');
  assert(shown(empty), 'CDU/CSU + Verkehr: the empty note is hidden although no row matches');
  expectCount('0 von 4 Abstimmungen', 'CDU/CSU + Verkehr');
  assert(!shown(mai) && !shown(april), 'CDU/CSU + Verkehr: a month heading stays up with no row');

  // 6. Clear: every pressed chip again restores the list.
  cdu.click();
  verkehr.click();
  expectRows([true, true, true, true], 'cleared');
  assert(!shown(empty) && shown(mai) && shown(april), 'cleared: note or headings wrong');
  expectCount('4 Abstimmungen', 'cleared');
  assert([spd, cdu, verkehr, gesundheit, untagged].every(unpressed), 'cleared: a chip is still pressed');

  // 5. Month headings follow their rows.
  gesundheit.click();
  expectRows([false, true, true, false], 'Gesundheit');
  assert(shown(mai) && shown(april), 'Gesundheit: both months have a row, both headings show');
  gesundheit.click();
  untagged.click();
  expectRows([false, false, false, true], 'untagged');
  assert(!shown(mai) && shown(april), 'untagged: the Mai heading stays up with no row under it');
  expectCount('1 von 4 Abstimmungen', 'untagged');
  untagged.click();
  expectRows([true, true, true, true], 'cleared again');
  expectCount('4 Abstimmungen', 'cleared again');
  return { rows: rows.length, months: headings.length };
})
