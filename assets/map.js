'use strict';
(async function () {
  const catalogue = document.querySelector('#cap-catalogue');
  const search = document.querySelector('#cap-filter');
  const count = document.querySelector('#cap-count');
  function filter() {
    const query = search.value.trim().toLowerCase();
    let visible = 0;
    catalogue.querySelectorAll('.capability').forEach(el => {
      el.hidden = !el.dataset.search.includes(query);
      if (!el.hidden) visible++;
    });
    count.textContent = `${visible} capabilities shown`;
  }
  search.addEventListener('input', filter); filter();
  const grid = document.querySelector('.workbench-map');
  const toggles = Array.from(document.querySelectorAll('[data-region]'));
  const detail = document.querySelector('#region-detail');
  const preset = document.querySelector('#layout-preset');
  let caps;
  try {
    const script = document.querySelector('script[src$="map.js"]');
    const response = await fetch(new URL('capabilities.json', script.src));
    if (!response.ok) throw new Error('catalogue HTTP '+response.status);
    caps = await response.json();
  } catch (_) {
    detail.textContent = 'Interactive details could not load. Read the complete source-linked catalogue below, or use the local HTTP preview.';
    return;
  }
  function select(id) {
    const c = caps.find(x => x.id === id);
    if (!c) return;
    grid.querySelectorAll('[data-cap]').forEach(button => button.setAttribute('aria-pressed',String(button.dataset.cap === id)));
    detail.replaceChildren();
    const heading = document.createElement('h3'); heading.textContent = c.name;
    const purpose = document.createElement('p'); purpose.textContent = c.purpose;
    const strategy = document.createElement('p'); strategy.textContent = c.strategy;
    const link = document.createElement('a'); link.href = '#cap-'+id; link.textContent = 'Read the capability and source location';
    detail.append(heading,purpose,strategy,link);
  }
  function layout() {
    toggles.forEach(toggle => {
      grid.classList.toggle('no-'+toggle.dataset.region,!toggle.checked);
      const button = grid.querySelector('[data-cap="'+toggle.dataset.region+'"]');
      button.hidden = !toggle.checked;
      if (button.hidden && button.getAttribute('aria-pressed') === 'true') select('editor');
    });
  }
  grid.querySelectorAll('[data-cap]').forEach(button => button.addEventListener('click',() => select(button.dataset.cap)));
  toggles.forEach(toggle => toggle.addEventListener('change',layout));
  preset.addEventListener('change',() => {
    toggles.forEach(toggle => {toggle.checked = !(preset.value === 'research' && toggle.dataset.region === 'auxiliarybar');});
    layout();
  });
  document.querySelector('#reset-map').addEventListener('click',() => {preset.value='full';toggles.forEach(t=>{t.checked=true;});layout();select('editor');});
  select('editor'); layout();
})();
