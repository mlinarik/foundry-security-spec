"use strict";
let bearer = "";
let generation = 0;
const byId = (id) => document.getElementById(id);
async function read(path) {
  const response = await fetch(path, {headers: {Authorization: `Bearer ${bearer}`}, cache: "no-store", credentials: "omit", redirect: "error"});
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || "Request failed");
  return body;
}
byId("connect").addEventListener("click", async () => {
  const current = ++generation;
  bearer = byId("token").value;
  byId("token").value = "";
  byId("connection").textContent = "Connecting";
  try {
    const installation = await read("/v1/installation");
    if (current !== generation) return;
    byId("installation").textContent = JSON.stringify(installation, null, 2);
    byId("connection").textContent = "Connected";
    if (installation.active_evaluation_id) {
      const status = await read(`/v1/evaluations/${encodeURIComponent(installation.active_evaluation_id)}/status`);
      if (current === generation) byId("status").textContent = JSON.stringify(status, null, 2);
    }
  } catch (error) {
    if (current === generation) byId("connection").textContent = error.message;
  }
});
byId("disconnect").addEventListener("click", () => {
  ++generation; bearer = ""; byId("token").value = "";
  byId("connection").textContent = "Disconnected";
  byId("installation").textContent = "No authenticated state loaded.";
  byId("status").textContent = "No evaluation loaded.";
});
