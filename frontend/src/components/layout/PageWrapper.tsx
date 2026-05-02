import { TopBar } from "./TopBar";

interface PageWrapperProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}

export function PageWrapper({ title, subtitle, children }: PageWrapperProps) {
  return (
    <div className="ml-64 flex flex-col min-h-screen bg-gray-50">
      <TopBar title={title} />
      <main className="flex-1 p-6">
        {subtitle && (
          <p className="text-sm text-gray-500 -mt-1 mb-5">{subtitle}</p>
        )}
        {children}
      </main>
    </div>
  );
}
