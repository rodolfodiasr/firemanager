import { PageWrapper } from "../components/layout/PageWrapper";

export function Settings() {
  return (
    <PageWrapper title="Configurações">
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Configurações do sistema</h2>
        <p className="text-sm text-gray-500">Em desenvolvimento — v0.5</p>
      </div>
    </PageWrapper>
  );
}
