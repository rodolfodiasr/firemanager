import { useState, useRef, useEffect } from "react";
import { Building2, ChevronDown, Check } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";

export function TenantSwitcher() {
  const { tenant, selectTenant, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [myTenants, setMyTenants] = useState<{ id: string; name: string; slug: string }[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    import("../../api/client").then(({ default: apiClient }) => {
      apiClient
        .get<{ id: string; name: string; slug: string }[]>("/auth/me/tenants")
        .then((r) => setMyTenants(r.data))
        .catch(() => {});
    });
  }, [user?.id]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  if (!tenant || myTenants.length <= 1) {
    return (
      <span className="flex items-center gap-1.5 text-sm text-gray-600 font-medium">
        <Building2 size={14} className="text-brand-500" />
        {tenant?.name ?? "—"}
      </span>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-sm text-gray-700 font-medium hover:text-brand-600 transition-colors"
      >
        <Building2 size={14} className="text-brand-500" />
        {tenant.name}
        <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl border border-gray-200 shadow-lg z-50 py-1 overflow-hidden">
          {myTenants.map((t) => (
            <button
              key={t.id}
              onClick={() => { selectTenant(t.id); setOpen(false); }}
              className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-left hover:bg-gray-50 transition-colors"
            >
              <span className={t.id === tenant.id ? "font-semibold text-brand-600" : "text-gray-700"}>
                {t.name}
              </span>
              {t.id === tenant.id && <Check size={14} className="text-brand-500" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
