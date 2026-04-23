import { PageWrapper } from "../components/layout/PageWrapper";

export function Audit() {
  return (
    <PageWrapper title="Auditoria">
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Dashboard de Auditoria</h2>
        <p className="text-sm text-gray-500">Motor de auditoria disponível na v0.5</p>
      </div>
    </PageWrapper>
  );
}
