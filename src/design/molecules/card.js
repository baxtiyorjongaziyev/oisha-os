// src/design/molecules/card.js
// Molecule: Deal Card
// Combines atomic styles and SVG icon support.
// Usage: import renderCard from './card.js';
//        container.innerHTML = renderCard(deal);

import { renderDrawer } from '../../static/sotuv_drawer.js'; // Assuming drawer function is exported

const cardTemplate = (deal) => `
<div class="card" data-id="${deal.id}">
  <div class="card-header font-h5 mt-1 mb-1">
    <span class="card-title">${deal.title}</span>
    <span class="card-status ${deal.status.toLowerCase()}">${deal.status}</span>
  </div>
  <div class="card-body font-base p-2">
    <p class="card-summary">${deal.summary || ''}</p>
    <div class="card-icons mt-1">
      ${deal.priority === 'high' ? '<svg class="icon"><use href="/static/icons/rocket.svg#icon"></use></svg>' : ''}
      ${deal.isNew ? '<svg class="icon"><use href="/static/icons/smile.svg#icon"></use></svg>' : ''}
    </div>
  </div>
</div>
`;

export function renderCard(deal) {
  const el = document.createElement('div');
  el.innerHTML = cardTemplate(deal);
  const card = el.firstElementChild;
  // Click handler to open drawer with full lead object (optimistic rendering)
  card.addEventListener('click', () => {
    // If the full lead object is already present, pass it directly.
    renderDrawer(deal);
  });
  return card;
}

/*
  Styling expectations (requires atoms.css to be loaded globally):
  .card { background: var(--color-neutral-100); border-radius: var(--radius-md); box-shadow: var(--shadow-sm); cursor: pointer; }
  .card:hover { box-shadow: var(--shadow-md); }
  .card-status { float: right; font-size: var(--font-size-sm); opacity: 0.8; }
  .card-status.high { color: var(--color-danger); }
  .card-status.low { color: var(--color-success); }
*/
