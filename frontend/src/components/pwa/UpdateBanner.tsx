import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

export function UpdateBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const handler = () => setVisible(true);
    window.addEventListener("pwa-update-available", handler);
    return () => window.removeEventListener("pwa-update-available", handler);
  }, []);

  const handleUpdate = () => {
    // Pede ao SW ativo para ceder o controle ao novo SW
    navigator.serviceWorker?.getRegistration().then((reg) => {
      reg?.waiting?.postMessage({ type: "SKIP_WAITING" });
    });
    window.location.reload();
  };

  if (!visible) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] flex items-center justify-between gap-3 bg-brand-600 text-white px-4 py-2.5 shadow-lg">
      <p className="text-sm font-medium">
        Nova versão disponível — atualize para continuar usando a plataforma.
      </p>
      <button
        onClick={handleUpdate}
        className="flex items-center gap-1.5 bg-white text-brand-600 text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-gray-100 shrink-0 transition-colors"
      >
        <RefreshCw size={13} />
        Atualizar agora
      </button>
    </div>
  );
}
