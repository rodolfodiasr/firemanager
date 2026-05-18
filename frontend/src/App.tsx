import { useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { AppRouter } from "./router";
import { useAuthStore } from "./store/authStore";
import { StagingBanner } from "./components/layout/StagingBanner";
import { AgentDrawer } from "./components/layout/AgentDrawer";
import { UpdateBanner } from "./components/pwa/UpdateBanner";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthInit() {
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) {
      fetchMe();
    }
  }, [isAuthenticated, fetchMe]);

  return null;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* WCAG 2.1 AA — skip navigation link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[9999] focus:bg-brand-600 focus:text-white focus:px-4 focus:py-2 focus:rounded-lg focus:text-sm focus:font-medium focus:outline-none focus:ring-2 focus:ring-white"
        >
          Pular para o conteúdo
        </a>
        <UpdateBanner />
        <StagingBanner />
        <AuthInit />
        <AppRouter />
        <AgentDrawer />
        <Toaster
          position="top-right"
          toastOptions={{
            success: { "aria-live": "polite" } as React.HTMLAttributes<HTMLDivElement>,
            error: { role: "alert" } as React.HTMLAttributes<HTMLDivElement>,
          }}
        />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
