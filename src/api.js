async function request(path, options = {}) {
  let response;
  try {
    response = await fetch("/api" + path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
      body: options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body,
    });
  } catch {
    throw new Error("The local service is not responding. Start the API and reload this page.");
  }
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof data === "string" ? data : data.detail || data.message || "The request could not be completed.";
    throw new Error(message);
  }
  return data;
}

export const api = {
  health: () => request("/health"),
  overview: () => request("/overview"),
  hospitals: () => request("/hospitals"),
  inventory: (params = {}) => request("/inventory?" + new URLSearchParams(params)),
  suppliers: (medicine) => request("/suppliers" + (medicine ? "?medicine_id=" + encodeURIComponent(medicine) : "")),
  disruptions: () => request("/disruptions"),
  workflow: () => request("/workflow/latest"),
  recommendations: () => request("/recommendations"),
  approvals: () => request("/approvals"),
  shipments: () => request("/shipments"),
  audit: () => request("/audit"),
  analytics: () => request("/analytics"),
  settings: () => request("/settings"),
  simulate: (scenario) => request("/disruptions/simulate", { method: "POST", body: { scenario } }),
  reset: () => request("/demo/reset", { method: "POST" }),
  decide: (id, body) => request("/approvals/" + encodeURIComponent(id) + "/decision", { method: "POST", body }),
  procure: (supplier_id) => request("/recommendations/procure", { method: "POST", body: { supplier_id } }),
  order: (body) => request("/orders", { method: "POST", body }),
  recordSale: (body) => request("/sales", { method: "POST", body }),
  advance: (id, status) => request("/shipments/" + encodeURIComponent(id) + "/advance?status=" + encodeURIComponent(status), { method: "POST" }),
  saveSettings: (body) => request("/settings", { method: "PUT", body }),
  checkProvider: () => request("/settings/check", { method: "POST" }),
};
