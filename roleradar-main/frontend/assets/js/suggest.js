/*
 * Small autocomplete dropdown for text inputs.
 *   attachSuggest(input, getItems, onPick?)
 * getItems(query) returns an array of strings; the dropdown shows up to MAX_SHOWN of them under
 * the input (which must sit inside a position:relative wrapper). Arrow keys move, Enter picks,
 * Escape closes, clicking outside closes. Picking fills the input and fires an 'input' event.
 */
const SUGGEST_MAX_SHOWN = 7;

function attachSuggest(input, getItems, onPick) {
  const list = document.createElement('ul');
  list.className = 'suggest-list';
  list.setAttribute('role', 'listbox');
  input.parentElement.appendChild(list);
  input.setAttribute('autocomplete', 'off');
  input.setAttribute('aria-autocomplete', 'list');

  let items = [];
  let active = -1;

  function close() {
    list.classList.remove('open');
    active = -1;
  }

  function highlight(text, query) {
    const i = text.toLowerCase().indexOf(query.toLowerCase());
    if (i < 0 || !query) return escapeHtml(text);
    return escapeHtml(text.slice(0, i)) + '<strong>' + escapeHtml(text.slice(i, i + query.length)) + '</strong>' + escapeHtml(text.slice(i + query.length));
  }

  function setActive(next) {
    const rows = list.querySelectorAll('li');
    rows.forEach(r => r.classList.remove('active'));
    active = next;
    if (rows[active]) { rows[active].classList.add('active'); rows[active].scrollIntoView({ block: 'nearest' }); }
  }

  function pick(value) {
    input.value = value;
    input.dispatchEvent(new Event('input', { bubbles: true })); // lets other listeners react; this re-opens the list...
    close();                                                     // ...so close after
    if (onPick) onPick(value);
  }

  function refresh() {
    const query = input.value.trim();
    items = getItems(query).slice(0, SUGGEST_MAX_SHOWN);
    if (!items.length) { close(); return; }
    list.innerHTML = items.map((t, i) => `<li role="option" data-i="${i}">${highlight(t, query)}</li>`).join('');
    list.classList.add('open');
    active = -1;
  }

  input.addEventListener('input', refresh);
  input.addEventListener('focus', refresh);
  input.addEventListener('keydown', (e) => {
    if (!list.classList.contains('open')) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((active + 1) % items.length); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((active - 1 + items.length) % items.length); }
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); pick(items[active]); }
    else if (e.key === 'Escape') close();
  });
  // mousedown (not click) so it lands before the input's blur closes the list
  list.addEventListener('mousedown', (e) => {
    const li = e.target.closest('li');
    if (li) { e.preventDefault(); pick(items[Number(li.dataset.i)]); }
  });
  document.addEventListener('click', (e) => { if (!input.parentElement.contains(e.target)) close(); });
  input.addEventListener('blur', () => setTimeout(close, 120));
}
