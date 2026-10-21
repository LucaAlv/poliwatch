// Value: protects=same-URL speech clicks honor inherited base targets; fails_when=the click handler ignores <base target>; why_new=anchor target tests do not exercise the inherited target branch; seam=none; no_claim=browser behavior outside Chrome/Chromium
(async function () {
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const tick = () => new Promise(resolve => requestAnimationFrame(() => setTimeout(resolve, 0)));
  if (document.querySelector('details#speech-4-ID0')) {
    const first = document.getElementById('speech-4-ID0');
    const second = document.getElementById('speech-4-ID1');
    const keyboardLink = document.querySelector('[data-speech-keyboard-check]');
    if (keyboardLink) {
      assert(first.open && location.href === keyboardLink.href,
        'real keyboard Enter must reopen speech without changing the fragment');
      return { keyboardEnter: 'passed' };
    }
    assert(location.hash === '#speech-4-ID0' && first.open && !second.open,
      'initial speech fragment must open only its card');
    const link = document.createElement('a');
    link.href = location.href;
    link.innerHTML = '<span>Repeat speech link</span>';
    first.before(link);
    first.querySelector('summary').click(); await tick();
    assert(!first.open, 'speech must close before repeated activation');
    const originalUrl = location.href;
    let prevented;
    const observe = event => { prevented = event.defaultPrevented; };
    window.addEventListener('click', observe);
    link.firstElementChild.click(); await tick();
    window.removeEventListener('click', observe);
    assert(first.open && location.href === originalUrl && prevented === false,
      'nested same-URL click must reopen speech while preserving native navigation');
    assert(Math.abs(first.getBoundingClientRect().top) < innerHeight,
      'reopened speech must scroll into view');

    for (const hash of ['#speech-4-ID1', '#%E0%A4%A', '#speech-missing', '#top-4']) {
      first.open = false; second.open = false;
      link.href = hash; link.click(); await tick();
      assert(!first.open && second.open === (hash === '#speech-4-ID1'),
        'changed, malformed, missing or non-speech fragment revealed the wrong card: ' + hash);
      const before = [...document.querySelectorAll('details[open]')];
      link.click(); await tick();
      assert([...document.querySelectorAll('details[open]')].every(el => before.includes(el)),
        'repeated invalid fragment opened an unrelated disclosure');
    }
    link.href = '#speech-4-ID0'; link.click(); await tick();
    first.open = false;
    // Observe default handling after the runtime, then suppress navigation in this test only.
    const suppress = event => { prevented = event.defaultPrevented; event.preventDefault(); };
    window.addEventListener('click', suppress);
    const unchanged = location.href;
    for (const options of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }]) {
      prevented = undefined;
      link.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, ...options }));
      assert(!first.open && prevented === false, 'modified/non-primary click must keep native handling');
    }
    for (const [attribute, value] of [['download', 'speech.html'], ['target', '_blank'], ['target', 'other-frame']]) {
      link.setAttribute(attribute, value); link.click();
      assert(!first.open && prevented === false, attribute + ' link must keep native handling');
      link.removeAttribute(attribute);
    }
    const base = document.createElement('base'); base.target = '_blank'; document.head.append(base);
    link.click();
    assert(!first.open && prevented === false, 'inherited base target must keep native handling');
    base.remove();
    const cancel = event => event.preventDefault();
    document.addEventListener('click', cancel);
    link.click();
    document.removeEventListener('click', cancel);
    assert(!first.open && prevented === true, 'canceled click must not reopen speech');
    for (const href of [unchanged.replace(location.origin, 'https://example.org'),
      unchanged.replace(location.pathname, '/another.html'), unchanged.replace('#', '?different=1#'), '#top-4']) {
      link.href = href; link.click();
      assert(!first.open && prevented === false, 'unrelated resolved URL must keep native handling: ' + href);
    }
    window.removeEventListener('click', suppress);
    assert(location.href === unchanged, 'test navigation suppression failed');
    link.href = unchanged;
    link.dataset.speechKeyboardCheck = '';
    link.focus();
    assert(document.activeElement === link && !first.open, 'ready for real keyboard Enter activation');
    // Use the browser driver's Enter key, then run this check again to verify the result.
    return { speechChecks: 'passed', keyboardEnter: 'pending on focused Repeat speech link' };
  }
  const root = document.querySelector('[data-bills-index]');
  if (!root && document.querySelector('.bill-detail-grid')) {
    assert(document.querySelectorAll('main').length === 1, 'detail must have one reading landmark');
    assert([...document.querySelectorAll('main section')].map(s => s.id).join(',') ===
      'verlauf,debatten,redner,abstimmungen,dokumente,quellen', 'detail source order changed');
    const speakers = [...document.querySelectorAll('.bill-speakers li')];
    assert(speakers.length === 15 && speakers.filter(e => e.checkVisibility()).length === 12,
      'detail must retain all speakers while initially showing twelve');
    document.querySelector('.bill-more-speakers summary').click();
    assert(speakers.every(e => e.checkVisibility()), 'speaker disclosure did not reveal everyone');
    assert(document.querySelectorAll('.bill-event-date').length === 1 &&
      document.querySelectorAll('.bill-events li a:not([data-bill-help])').length === 2,
      'same-date grouping must preserve both source links');
    assert(document.querySelector('.bill-votes a').href.startsWith('https://www.bundestag.de/'),
      'roll-call vote must keep its official source link');
    assert(document.documentElement.scrollWidth <= innerWidth, 'detail overflows the viewport');
    const timeline = document.querySelector('#verlauf').getBoundingClientRect();
    const documents = document.querySelector('#dokumente').getBoundingClientRect();
    if (innerWidth > 900) assert(documents.top - timeline.bottom <= 13,
      'speaker sidebar must not push documents away from the timeline');
    for (const link of document.querySelectorAll('.bill-section-nav a')) {
      const style = getComputedStyle(link);
      assert(parseFloat(style.paddingInlineStart) >= 12 && parseFloat(style.paddingBlockStart) >= 8,
        'section links need comfortable padding');
    }
    assert(speakers[0].querySelector('.bill-speech-links a').textContent.includes('Rede lesen'),
      'one speech should have a direct reading link');
    const speechList = speakers[1].querySelector('.bill-speaker-speeches');
    assert(!speechList.open && !speechList.querySelector('a').checkVisibility(),
      'multiple speech links should initially be collapsed');
    speechList.querySelector('summary').click();
    assert([...speechList.querySelectorAll('a')].length === 2 &&
      [...speechList.querySelectorAll('a')].every(a => a.checkVisibility() && a.hash.startsWith('#speech-')),
      'speech disclosure must reveal both direct speech links');
    const first = speakers[0];
    assert(first.querySelector('.bill-speaker-role').getBoundingClientRect().top >=
      first.querySelector('.bill-speaker-name').getBoundingClientRect().bottom,
      'speaker role overlaps the name');
    return { speakers: speakers.length, sections: 6, viewport: innerWidth };
  }
  assert(root, 'generated overview root is missing');
  const query = document.querySelector('[data-bill-search]');
  const year = document.querySelector('[data-bill-year]');
  const sort = document.querySelector('[data-bill-sort]');
  const reset = document.querySelector('[data-bill-reset]');
  const prev = document.querySelector('[data-bill-prev]');
  const next = document.querySelector('[data-bill-next]');
  const summary = document.querySelector('[data-bill-summary]');
  const rows = [...document.querySelectorAll('[data-bill-row]')];
  assert(document.querySelectorAll('[data-bill-row] h2 a').length === 41, 'each static result title must be the detail link');
  const visible = () => [...root.querySelectorAll('[data-bill-row]')].filter(row => !row.hidden);
  const change = async (el, value) => { el.focus(); el.value = value; el.dispatchEvent(new Event(el.matches('input') ? 'input' : 'change', { bubbles: true })); await tick(); };
  assert(rows.length === 41 && visible().length === 20, 'initialized overview should retain 41 static rows and show the first 20');
  assert(root.dataset.billReady === 'true' && !query.disabled && !year.disabled && !sort.disabled, 'successful initialization must enable controls');

  await change(query, '  21/9876  ');
  assert(visible().length === 1 && visible()[0].dataset.id === 'browser-00', 'secondary document number search failed');
  assert(new URL(location.href).searchParams.get('q') === '21/9876', 'search query was not reflected in URL');
  assert(document.activeElement === query, 'typing into search moved focus');
  await change(query, 'gesetzesvorhaben 04');
  assert(visible().length === 1 && visible()[0].dataset.id === 'browser-04', 'AND word matching failed');
  await change(query, 'COHORT');
  assert(visible().length === 20, '21 matching rows should paginate as 20 plus 1');
  await next.click(); await tick();
  assert(visible().length === 1, 'the 21st matching row should appear on page 2');
  await change(query, '21/');
  assert(visible().length === 20, '40 matching rows should paginate as 20 plus 20');
  await next.click(); await tick();
  assert(visible().length === 20, 'second page of 40 matching rows is incomplete');
  await change(query, 'no such bill');
  assert(visible().length === 0 && !document.querySelector('[data-bill-no-results]').hidden, 'no-match state was not shown');
  await change(sort, 'title');
  reset.focus();
  assert(document.activeElement === reset, 'reset must have focus before activation');
  await reset.click(); await tick();
  assert(reset.hidden && document.activeElement === query, 'hidden reset must return focus to search');
  assert(visible().length === 20 && sort.value === 'title', 'reset should restore results while preserving sort');
  assert(new URL(location.href).searchParams.get('sort') === 'title', 'reset dropped selected sort from URL');

  await change(query, '21/');
  await next.click(); await tick();
  assert(new URL(location.href).searchParams.get('page') === '2', 'reset setup must reach page two');
  reset.focus(); reset.click(); await tick();
  assert(reset.hidden && document.activeElement === query && query.value === '' && year.value === '' &&
    !new URL(location.href).searchParams.has('page') && sort.value === 'title',
    'focused reset must clear filters, return to page one and retain sort');

  await change(sort, 'date-asc');
  assert(visible()[0].dataset.id === 'browser-00', 'oldest-first ordering failed');
  await change(sort, 'date-desc');
  const years = [...year.options].map(option => option.value);
  assert(years.includes('2022') && years.includes('2024') && years.includes('2026'), 'year options missed populated years');
  await change(year, '2022');
  assert(visible().every(row => row.dataset.date.startsWith('2022-')), 'year filter returned another year or a missing date');
  await change(query, '21/');
  reset.focus(); reset.click(); await tick();
  assert(reset.hidden && document.activeElement === query && query.value === '' && year.value === '',
    'reset must clear both query and year and focus search');

  await change(sort, 'title');
  const titleFirsts = visible().slice(0, 2).map(row => row.dataset.id);
  assert(titleFirsts[0] === 'browser-01' && titleFirsts[1] === 'browser-02', 'German title ordering or deterministic normalized tie failed');
  await change(sort, 'date-desc');
  assert(visible().length === 20 && !next.disabled, 'first page should contain 20 rows and enable next');
  await next.click(); await tick();
  assert(new URL(location.href).searchParams.get('page') === '2', 'next page did not update URL');
  assert(visible().length === 20 && document.activeElement === summary, 'page 2 must show 20 rows and move focus to summary');
  await next.click(); await tick();
  assert(visible().length === 1 && new URL(location.href).searchParams.get('page') === '3', '41st result page failed');
  await next.click(); await tick();
  assert(new URL(location.href).searchParams.get('page') === '3', 'next on final page must not advance');

  const waitPop = () => new Promise(resolve => { const timer = setTimeout(resolve, 1000); addEventListener('popstate', () => { clearTimeout(timer); setTimeout(resolve, 0); }, { once: true }); });
  let popped = waitPop(); history.back(); await popped; await tick();
  assert(new URL(location.href).searchParams.get('page') === '2' && visible().length === 20, 'Back did not restore page 2');
  popped = waitPop(); history.forward(); await popped; await tick();
  assert(new URL(location.href).searchParams.get('page') === '3' && visible().length === 1, 'Forward did not restore page 3');

  await reset.click(); await tick();
  assert(visible().length === 20 && !new URL(location.href).searchParams.has('q') && !new URL(location.href).searchParams.has('year'), 'reset did not clear search/year');
  assert((new URL(location.href).searchParams.get('page') || '1') === '1', 'reset did not return to page one');
  assert(document.querySelector('[data-bill-no-results]').hidden, 'no-match message should be hidden after reset');
  const help = visible()[5].querySelector('[data-bill-help]');
  help.focus();
  await new Promise(resolve => setTimeout(resolve, 200));
  const tooltip = document.getElementById(help.dataset.billHelp);
  assert(!tooltip.hidden, 'keyboard focus scrolling must preserve the term explanation');
  const box = tooltip.getBoundingClientRect();
  assert(box.left >= 0 && box.right <= innerWidth && box.top >= 0 && box.bottom <= innerHeight,
    'term explanation must stay within the viewport');
  document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
  assert(tooltip.hidden && document.activeElement === help, 'Escape must dismiss explanation without moving focus');
  query.focus();
  return { rows: rows.length, pageSize: 20, currentPage: new URL(location.href).searchParams.get('page') || '1', url: location.href };
})
