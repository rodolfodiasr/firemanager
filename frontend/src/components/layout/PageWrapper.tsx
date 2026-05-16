import { useState } from "react";
import { useLocation } from "react-router-dom";
import { HelpCircle } from "lucide-react";
import { TopBar } from "./TopBar";
import { HelpDrawer } from "../help/HelpDrawer";
import { helpByRoute } from "../../data/helpContent";

interface PageWrapperProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function PageWrapper({ title, subtitle, children }: PageWrapperProps) {
  const [helpOpen, setHelpOpen] = useState(false);
  const { pathname } = useLocation();
  const help = helpByRoute[pathname];

  return (
    <div className="ml-64 flex flex-col min-h-screen bg-gray-50">
      <TopBar title={title} />
      <main id="main-content" className="flex-1 p-6" tabIndex={-1}>
        {(subtitle || help) && (
          <div className="flex items-center justify-between -mt-1 mb-5">
            {subtitle ? (
              <p className="text-sm text-gray-500">{subtitle}</p>
            ) : (
              <span />
            )}
            {help && (
              <button
                onClick={() => setHelpOpen(true)}
                aria-label={`Ajuda sobre ${title}`}
                title="Como usar este módulo"
                className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-brand-600 transition-colors"
              >
                <HelpCircle size={15} aria-hidden="true" />
                <span>Ajuda</span>
              </button>
            )}
          </div>
        )}
        {children}
      </main>

      {help && (
        <HelpDrawer
          isOpen={helpOpen}
          onClose={() => setHelpOpen(false)}
          help={help}
        />
      )}
    </div>
  );
}
