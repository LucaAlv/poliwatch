// Value: protects=the week radar's inline Politikfeld filter hides and shows rows by chip, shows the empty note, and the last visible row never keeps a bottom border; fails_when=a chip stops filtering, a hidden last row leaves the last visible row bordered (position-based :last-child), or the filter script throws at load; why_new=Python render tests assert markup but cannot run the inline script or evaluate computed borders; seam=none; no_claim=browser engines other than Chrome/Chromium
(async function () {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const list = document.querySelector('.radar-list');
  assert(list, 'radar list is missing');
  const rows = [...list.querySelectorAll('.radar-row')];
  assert(rows.length === 3, `expected 3 radar rows, got ${rows.length}`);
  const chip = (name) => document.querySelector(`[data-radar-chip="${name}"]`);
  const visible = () => rows.filter((row) => !row.hidden);
  const borders = () => rows.map((row) => getComputedStyle(row).borderBottomWidth);
  const empty = document.querySelector('[data-radar-empty]');
  const verkehr = chip('Verkehr'), gesundheit = chip('Gesundheit');
  assert(verkehr && gesundheit && empty, 'filter chips or the empty note are missing');

  assert(visible().length === 3, 'rows are hidden before any chip is pressed');
  assert(borders()[2] === '0px' && borders()[0] !== '0px', `initial borders wrong: ${borders()}`);

  // Rows are Verkehr, Gesundheit, Verkehr. Gesundheit hides the last row.
  gesundheit.click();
  assert(JSON.stringify(rows.map((row) => row.hidden)) === '[true,false,true]', 'Gesundheit did not show only the middle row');
  assert(gesundheit.getAttribute('aria-pressed') === 'true' && gesundheit.classList.contains('is-active'), 'chip state not set');
  assert(borders()[1] === '0px', `last visible row keeps its bottom border: ${borders()}`);
  assert(empty.hidden, 'empty note shown although a row matches');

  // Verkehr too (any match): all rows back, last row borderless, middle still bordered.
  verkehr.click();
  assert(visible().length === 3, 'two chips (any match) did not show all rows');
  assert(borders()[2] === '0px' && borders()[1] !== '0px', `borders after two chips wrong: ${borders()}`);

  // Only Verkehr: rows 0 and 2; row 2 is last.
  gesundheit.click();
  assert(JSON.stringify(rows.map((row) => row.hidden)) === '[false,true,false]', 'Verkehr did not show rows 1 and 3');
  assert(borders()[2] === '0px' && borders()[0] !== '0px', `Verkehr borders wrong: ${borders()}`);

  // Row 3 hidden by pressing Gesundheit alone after Verkehr off: covered above; clear everything.
  verkehr.click();
  assert(visible().length === 3 && empty.hidden, 'clearing the chips did not restore every row');
  assert(borders()[2] === '0px' && borders()[1] !== '0px', `borders after clearing wrong: ${borders()}`);
  return { rows: rows.length, borders: borders() };
})
