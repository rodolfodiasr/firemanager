import { useState, useRef, useEffect } from "react";
import { Building2, ChevronDown, Check, LogOut } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";

export function TenantSwitcher() {
  const { tenant, selectTenant, assumeTenant, exitAssumedTenant, user } = useAuth();
  const [open, setOpen] = useState(false);
  const [allTenants, setAllTenants] = useState<{ id: string; name: string; slug: string }[]>([]);
  const ref = useRef<HTMLDivElement>(null);

  const isSuperAdmin = user?.is_super_admin ?? false;

  useEffect(() => {
    if (!user) return;
    import("../../api/client").then(({ default: apiClient }) => {
      const endpoint = isSuperAdmin ? "/admin/tenants/overview" : "/auth/me/tenants";
      apiClient
        .get<{ id: string; name: string; slug: string }[]>(endpoint)
        .then((r) => setAllTenants(r.data))
        .catch(() => {});
    });
  }, [user?.id, isSuperAdmin]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleSelect = (id: string) => {
    if (isSuperAdmin) {
      assumeTenant(id);
    } else {
      selectTenant(id);
    }
    setOpen(false);
  };

  // Regular user with single tenant — static label
  if (!isSuperAdmin && (!tenant || allTenants.length <= 1)) {
    return (
      <span className="flex items-center gap-1.5 text-sm text-gray-600 font-medium">
        <Building2 size={14} className="text-brand-500" />
        {tenant?.name ?? "—"}
      </span>
    );
  }

  // Super admin with no tenant assumed — show selector button
  if (isSuperAdmin && !tenant) {
    return (
      <div className="relative" ref={ref}>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-1.5 text-sm font-medium text-amber-600 hover:text-amber-700 border border-amber-300 rounded-lg px-2.5 py-1 transition-colors"
        >
          <Building2 size={14} />
          Selecionar tenant
          <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
        {open && allTenants.length > 0 && (
          <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl border border-gray-200 shadow-lg z-50 py-1 overflow-hidden">
            {allTenants.map((t) => (
              <button
                key={t.id}
                onClick={() => handleSelect(t.id)}
                className="w-full px-4 py-2.5 text-sm text-left hover:bg-gray-50 transition-colors text-gray-700"
              >
                {t.name}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // Has a tenant — show name + dropdown (switch or exit for super admins)
  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-sm text-gray-700 font-medium hover:text-brand-600 transition-colors"
      >
        <Building2 size={14} className="text-brand-500" />
        {tenant!.name}
        <ChevronDown size={13} className={`transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 w-56 bg-white rounded-xl border border-gray-200 shadow-lg z-50 py-1 overflow-hidden">
          {allTenants.map((t) => (
            <button
              key={t.id}
              onClick={() => handleSelect(t.id)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-left hover:bg-gray-50 transition-colors"
            >
              <span className={t.id === tenant!.id ? "font-semibold text-brand-600" : "text-gray-700"}>
                {t.name}
              </span>
              {t.id === tenant!.id && <Check size={14} className="text-brand-500" />}
            </button>
          ))}

          {isSuperAdmin && (
            <>
              <div className="border-t border-gray-100 my-1" />
              <button
                onClick={() => { exitAssumedTenant(); setOpen(false); }}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-left hover:bg-red-50 text-red-600 transition-colors"
              >
                <LogOut size={13} />
                Sair do tenant
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
