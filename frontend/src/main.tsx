import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";
import "./i18n";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// ── PWA Service Worker ─────────────────────────────────────────────────────────
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .then((registration) => {
        // Verifica atualizações a cada 60 segundos enquanto o app está aberto
        setInterval(() => registration.update(), 60_000);

        // Quando um novo SW está instalado e aguardando
        registration.addEventListener("updatefound", () => {
          const newWorker = registration.installing;
          if (!newWorker) return;

          newWorker.addEventListener("statechange", () => {
            if (
              newWorker.state === "installed" &&
              navigator.serviceWorker.controller
            ) {
              // Dispara evento para o App exibir o banner de atualização
              window.dispatchEvent(new CustomEvent("pwa-update-available"));
            }
          });
        });
      })
      .catch(() => {
        // SW não registrou — modo degradado (sem cache offline)
      });

    // Quando SW atualizado envia mensagem de nova versão
    navigator.serviceWorker.addEventListener("message", (event) => {
      if (event.data?.type === "SW_UPDATED") {
        window.dispatchEvent(new CustomEvent("pwa-update-available"));
      }
    });
  });
}
