const tokenKey = "northstar-demo-token";
let accessToken = sessionStorage.getItem(tokenKey);
const money = (cents) => `$${(cents / 100).toFixed(2)}`;

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;
  const response = await fetch(path, { ...options, headers });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Request could not be completed.");
  return data;
}

function showMessage(selector, message, isError = false) {
  const element = document.querySelector(selector);
  element.textContent = message;
  element.classList.toggle("error", isError);
}

async function refreshCart() {
  if (!accessToken) return;
  try {
    const cart = await api("/api/cart");
    document.querySelector("#cart-count").textContent = cart.items.reduce((sum, item) => sum + item.quantity, 0);
    const container = document.querySelector("#cart-items");
    container.replaceChildren();
    if (!cart.items.length) {
      container.textContent = "Your bag is waiting for something good.";
      return;
    }
    for (const item of cart.items) {
      const row = document.createElement("div");
      row.className = "cart-row";
      const name = document.createElement("span");
      name.textContent = `${item.name} × ${item.quantity}`;
      const total = document.createElement("strong");
      total.textContent = money(item.line_total_cents);
      row.append(name, total);
      container.append(row);
    }
    const total = document.createElement("div");
    total.className = "cart-total";
    total.textContent = `Total ${money(cart.total_cents)}`;
    container.append(total);
  } catch (error) {
    showMessage("#catalog-message", error.message, true);
  }
}

document.querySelector("#product-search").addEventListener("input", (event) => {
  const term = event.target.value.trim().toLowerCase();
  let visible = 0;
  document.querySelectorAll(".product-card").forEach((card) => {
    const matches = card.dataset.productName.includes(term);
    card.hidden = !matches;
    if (matches) visible += 1;
  });
  document.querySelector("#no-results").hidden = visible > 0;
});

document.querySelectorAll(".add-button").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!accessToken) {
      showMessage("#catalog-message", "Create a demo account first to add items to your bag.", true);
      document.querySelector("#account").scrollIntoView({ behavior: "smooth" });
      return;
    }
    try {
      await api("/api/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: Number(button.dataset.productId), quantity: 1 }),
      });
      showMessage("#catalog-message", `${button.dataset.productName} added to your bag.`);
      await refreshCart();
    } catch (error) {
      showMessage("#catalog-message", error.message, true);
    }
  });
});

document.querySelector("#register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const credentials = { email: form.get("email"), password: form.get("password") };
  try {
    await api("/api/register", { method: "POST", body: JSON.stringify(credentials) });
    const login = await api("/api/login", { method: "POST", body: JSON.stringify(credentials) });
    accessToken = login.access_token;
    sessionStorage.setItem(tokenKey, accessToken);
    showMessage("#account-message", "Demo account created. Your bag is ready.");
    await refreshCart();
  } catch (error) {
    showMessage("#account-message", error.message, true);
  }
});

document.querySelector("#checkout-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const checkoutForm = event.currentTarget;
  if (!accessToken) {
    showMessage("#checkout-message", "Create a demo account before checkout.", true);
    return;
  }
  const form = new FormData(checkoutForm);
  try {
    const result = await api("/api/checkout", {
      method: "POST",
      body: JSON.stringify({ full_name: form.get("full_name"), email: form.get("email") }),
    });
    showMessage("#checkout-message", `Demo order #${result.order_id} placed for ${money(result.total_cents)}. No payment was collected.`);
    checkoutForm.reset();
    await refreshCart();
  } catch (error) {
    showMessage("#checkout-message", error.message, true);
  }
});

refreshCart();
