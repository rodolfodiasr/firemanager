import { TopBar } from "./TopBar";

interface PageWrapperProps {
  title: string;
  children: React.ReactNode;
}

export function PageWrapper({ title, children }: PageWrapperProps) {
  return (
    <div className="ml-64 flex flex-col min-h-screen bg-gray-50">
      <TopBar title={title} />
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
