import { Sparkles } from "lucide-react";
import { useAssistantStore } from "../../store/assistantStore";
import { useAuthStore } from "../../store/authStore";
import { useLocation } from "react-router-dom";

export function AssistantFab() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();
  const { isOpen, toggle } = useAssistantStore();

  const skip =
    !isAuthenticated ||
    ["/login", "/invite"].some((p) => location.pathname.startsWith(p));

  if (skip || isOpen) return null;

  return (
    <button
      onClick={toggle}
      title="AI Assistant"
      className="fixed bottom-24 right-6 z-40 w-12 h-12 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-xl flex items-center justify-center transition-transform hover:scale-105"
    >
      <Sparkles size={20} />
    </button>
  );
}
