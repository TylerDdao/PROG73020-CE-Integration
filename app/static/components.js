// loads header and footer into html files

async function loadComponent(id, file) {
  const res = await fetch(file);
  const html = await res.text();
  document.getElementById(id).innerHTML = html;
}

loadComponent('header-placeholder', '/static/header.html');
loadComponent('footer-placeholder', '/static/footer.html');

function openPanel() {
    document.getElementById('accountPanel').classList.add('open');
    document.getElementById('overlay').classList.add('open');
}

function closePanel() {
    document.getElementById('accountPanel').classList.remove('open');
    document.getElementById('overlay').classList.remove('open');
    document.getElementById('accountBtn').focus();
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closePanel();
});

const cartItems = JSON.parse(localStorage.getItem("cart")) || [];

const list = document.getElementById("cart-list");

cartItems.forEach(item => {
  const li = document.createElement("li");
  li.className = "list-group-item d-flex justify-content-between align-items-center py-3";

  li.innerHTML = `
    <div>
      <div class="fw-semibold">${item.productName}</div>
      <div class="text-muted small">${item.productId}</div>
    </div>
    <span class="badge bg-success-subtle text-success-emphasis rounded-pill px-3 py-2">
      ${item.quantity} ${item.unit}
    </span>
  `;

  list.appendChild(li);
});