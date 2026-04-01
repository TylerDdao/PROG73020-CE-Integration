document.addEventListener("DOMContentLoaded", () => {
  // ── Delivery preference toggle ──────────────────────
  const dropOff = document.getElementById("dropOffOption");
  const signature = document.getElementById("signatureOption");

  if (dropOff && signature) {
    dropOff.addEventListener("click", () => {
      dropOff.classList.add("active");
      signature.classList.remove("active");
    });

    signature.addEventListener("click", () => {
      signature.classList.add("active");
      dropOff.classList.remove("active");
    });
  }

  // ── Place order ─────────────────────────────────────
  const btn = document.getElementById("placeOrderBtn");

  btn.addEventListener("click", async () => {
    const deliveryPref = document.querySelector(".delivery-option.active")?.id === "signatureOption"
      ? "signature"
      : "drop_off";

    try {
      const response = await fetch("/checkout/submit", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: "Order placed from UI",
          delivery_preference: deliveryPref
        })
      });

      const data = await response.json();

      if (data.success) {
        alert("Order placed successfully!");
        window.location.href = "/";
      } else {
        alert("Order failed!");
      }

    } catch (err) {
      console.error(err);
      alert("Something went wrong");
    }
  });
});