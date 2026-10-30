// Value: protects=current-only comparison rows retain their values and use three columns at 1440px and 700px, two columns with a full-row bar at 375px, without viewport overflow; ordinary comparisons keep their delta chips; fails_when=the responsive grid reserves an empty delta track, the mobile bar no longer spans its row, current values disappear, or comparison deltas are suppressed; why_new=Python render tests assert markup but cannot evaluate computed responsive layout; seam=none; no_claim=browser engines other than Chrome/Chromium
(async function () {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const section = document.querySelector('.week-compare');
  assert(section, 'week comparison section is missing');
  const currentOnly = location.pathname.endsWith('current-only.html');
  const list = section.querySelector('.week-list');
  assert(list, 'fraction list is missing');

  if (currentOnly) {
    assert(list.classList.contains('week-list-current-only'), 'missing current-only layout class');
    assert(!section.querySelector('.week-delta'), 'current-only panel contains a delta chip');
    assert(!section.querySelector('.week-metric-foot'), 'current-only panel contains a metric footer');
    const metrics = [...section.querySelectorAll('.week-metric')].map(el => [
      el.querySelector('span').textContent.trim(), el.querySelector('strong').textContent.trim(),
    ]);
    assert(JSON.stringify(metrics) === JSON.stringify([
      ['Reden', '2'], ['Tagesordnungspunkte', '1'], ['Redetext (Zeichen)', '200'],
    ]), `current metric values changed: ${JSON.stringify(metrics)}`);
    const shares = [...list.querySelectorAll('.week-row')].map(row => [
      row.querySelector('.week-label').textContent.trim(), row.querySelector('strong').textContent.trim(),
    ]).sort((a, b) => a[0].localeCompare(b[0]));
    assert(JSON.stringify(shares) === JSON.stringify([['AfD', '50,0%'], ['SPD', '50,0%']]),
      `current faction shares changed: ${JSON.stringify(shares)}`);

    const row = list.querySelector('.week-row');
    const label = row.querySelector('.week-label').getBoundingClientRect();
    const bar = row.querySelector('.week-bar');
    const barRect = bar.getBoundingClientRect();
    const columns = getComputedStyle(row).gridTemplateColumns.trim().split(/\s+/).length;
    const expectedColumns = innerWidth <= 460 ? 2 : 3;
    assert(columns === expectedColumns, `${innerWidth}px expected ${expectedColumns} columns, got ${columns}`);
    if (innerWidth <= 460) {
      assert(getComputedStyle(bar).gridColumnEnd === '-1', 'mobile bar must span the full row');
      assert(barRect.top > label.top, 'mobile bar must render below the label and percentage');
      assert(Math.abs(barRect.width - row.getBoundingClientRect().width) < 1, 'mobile bar must span the row width');
    }
    assert(document.documentElement.scrollWidth <= innerWidth, 'page overflows the viewport horizontally');
    return { viewport: innerWidth, columns, barSpansRow: innerWidth <= 460, noOverflow: true };
  }

  assert(!list.classList.contains('week-list-current-only'), 'ordinary comparison got current-only layout');
  assert(section.querySelector('.week-delta'), 'ordinary comparison lost its delta chips');
  return { viewport: innerWidth, comparisonDeltas: section.querySelectorAll('.week-delta').length };
})
