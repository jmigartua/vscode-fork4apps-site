'use strict';
(function () {
  const button = document.querySelector('.mobile-nav-toggle');
  const sections = document.querySelector('#nav-sections');
  if (!button || !sections) return;
  const mobile = matchMedia('(max-width: 760px)');
  let expanded = !mobile.matches;
  function apply() {
    sections.hidden = mobile.matches && !expanded;
    button.setAttribute('aria-expanded', String(!sections.hidden));
    button.textContent = sections.hidden ? 'Show site sections' : 'Hide site sections';
  }
  button.classList.add('ready');
  button.addEventListener('click', () => {expanded = !expanded;apply();});
  mobile.addEventListener('change', () => {expanded = !mobile.matches;apply();});
  apply();
})();
