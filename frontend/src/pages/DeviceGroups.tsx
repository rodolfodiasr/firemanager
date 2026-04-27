import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  FolderOpen, Plus, Layers, Shield, Route, Network,
  Pencil, Trash2, Sparkles, Loader2, AlertCircle, ChevronRight,
} from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageWrapper } from "../components/layout/PageWrapper";
import { EmptyState } from "../components/shared/EmptyState";
import { ConfirmModal } from "../components/shared/ConfirmModal";
import { GroupModal } from "../components/device_groups/GroupModal";
import { deviceGroupsApi } from "../api/device_groups";
import { useAuthStore } from "../store/authStore";
import type { DeviceGroup } from "../types/device_group";

const CATEGORY_ICON: Record<string, React.ElementType> = {
  firewall: Shield,
  router: Route,
  switch: Network,
  l3_switch: Layers,
};

const CATEGORY_LABEL: Record<string, string> = {
  firewall: "Firewall",
  router: "Roteador",
  switch: "Switch",
  l3_switch: "Switch L3",
};

function CategoryBadge({ category, count }: { category: string; count: number }) {
  const Icon = CATEGORY_ICON[category] ?? Layers;
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-600 rounded-full px-2 py-0.5">
      <Icon size={10} />
      {CATEGORY_LABEL[category] ?? category}
      <span className="font-medium">{count}</span>
    </span>
  );
}

interface ApplyPanelProps {
  group: DeviceGroup;
  onDone: () => void;
}

function ApplyPanel({ group, onDone }: ApplyPanelProps) {
  const navigate = useNavigate();
  const [input, setInput] = useState("");

  const applyMut = useMutation({
    mutationFn: () => deviceGroupsApi.createBulkJob(group.id, input),
    onSuccess: (job) => {
      onDone();
      navigate(`/bulk-jobs/${job.id}`);
    },
  });

  return (
    <div className="mt-3 pt-3 border-t border-gray-100">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        rows={2}
        autoFocus
        placeholder="Ex: Bloquear portas não utilizadas e aplicar VLAN 10"
        className="w-full border rounded-lg px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
      />
      {applyMut.isError && (
        <div className="flex items-center gap-1 text-red-600 text-xs mt-1">
          <AlertCircle size={11} />
          {(applyMut.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
            ?? "Erro ao iniciar operação."}
        </div>
      )}
      <div className="flex justify-end gap-2 mt-2">
        <button
          onClick={onDone}
          className="text-xs text-gray-500 hover:text-gray-700"
        >
          Cancelar
        </button>
        <button
          onClick={() => applyMut.mutate()}
          disabled={input.trim().length < 5 || applyMut.isPending}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50"
        >
          {applyMut.isPending ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
          {applyMut.isPending ? "Processando IA..." : "Aplicar"}
        </button>
      </div>
    </div>
  );
}

interface GroupCardProps {
  group: DeviceGroup;
  onEdit: (g: DeviceGroup) => void;
  onDelete: (id: string) => void;
  canWrite: boolean;
}

function GroupCard({ group, onEdit, onDelete, canWrite }: GroupCardProps) {
  const [applying, setApplying] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="bg-brand-50 text-brand-600 p-2 rounded-lg shrink-0">
            <FolderOpen size={16} />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 truncate">{group.name}</h3>
            {group.description && (
              <p className="text-xs text-gray-400 truncate">{group.description}</p>
            )}
          </div>
        </div>
        {canWrite && (
          <div className="flex items-center gap-1 shrink-0 ml-2">
            <button
              onClick={() => onEdit(group)}
              className="p-1.5 text-gray-400 hover:text-gray-600 rounded"
              title="Editar"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={() => onDelete(group.id)}
              className="p-1.5 text-gray-400 hover:text-red-500 rounded"
              title="Remover"
            >
              <Trash2 size={13} />
            </button>
          </div>
        )}
      </div>

      {/* Device count + category breakdown */}
      <div className="flex items-center gap-2 flex-wrap mb-1">
        <span className="text-xs font-medium text-gray-500">
          {group.device_count} dispositivo{group.device_count !== 1 ? "s" : ""}
        </span>
        {Object.entries(group.category_counts).map(([cat, cnt]) => (
          <CategoryBadge key={cat} category={cat} count={cnt} />
        ))}
      </div>

      {/* Apply panel */}
      {canWrite && (
        applying
          ? <ApplyPanel group={group} onDone={() => setApplying(false)} />
          : (
            <button
              onClick={() => setApplying(true)}
              className="flex items-center gap-1.5 text-xs text-brand-600 hover:text-brand-700 font-medium mt-3"
            >
              <Sparkles size={12} />
              Aplicar operação neste grupo
              <ChevronRight size={12} />
            </button>
          )
      )}
    </div>
  );
}

export function DeviceGroups() {
  const tenantRole = useAuthStore((s) => s.tenantRole);
  const canWrite = tenantRole !== "readonly";

  const qc = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editGroup, setEditGroup] = useState<DeviceGroup | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const { data: groups = [], isLoading } = useQuery<DeviceGroup[]>({
    queryKey: ["device-groups"],
    queryFn: deviceGroupsApi.list,
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deviceGroupsApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["device-groups"] }),
  });

  const handleDelete = () => {
    if (deleteId) {
      deleteMut.mutate(deleteId);
      setDeleteId(null);
    }
  };

  return (
    <PageWrapper title="Grupos de Dispositivos">
      <div className="flex justify-between items-center mb-6">
        <p className="text-sm text-gray-500">
          Agrupe dispositivos por site ou função para operações recorrentes em lote.
        </p>
        {canWrite && (
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700 transition-colors"
          >
            <Plus size={16} />
            Novo grupo
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <Loader2 size={16} className="animate-spin" />
          Carregando grupos...
        </div>
      ) : groups.length === 0 ? (
        <EmptyState
          title="Nenhum grupo criado"
          description="Crie grupos para organizar dispositivos por site ou função e aplicar operações em lote com facilidade."
          action={
            canWrite ? (
              <button
                onClick={() => setShowCreate(true)}
                className="px-4 py-2 bg-brand-600 text-white text-sm rounded-lg hover:bg-brand-700"
              >
                Criar primeiro grupo
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {groups.map((group) => (
            <GroupCard
              key={group.id}
              group={group}
              onEdit={(g) => setEditGroup(g as DeviceGroup)}
              onDelete={(id) => setDeleteId(id)}
              canWrite={canWrite}
            />
          ))}
        </div>
      )}

      {/* Create modal */}
      <GroupModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
      />

      {/* Edit modal — needs full detail with devices list */}
      {editGroup && (
        <EditGroupWrapper
          groupId={editGroup.id}
          onClose={() => setEditGroup(null)}
        />
      )}

      <ConfirmModal
        isOpen={!!deleteId}
        title="Remover grupo"
        description="Tem certeza que deseja remover este grupo? Os dispositivos não serão afetados."
        danger
        onConfirm={handleDelete}
        onCancel={() => setDeleteId(null)}
        confirmLabel="Remover"
      />
    </PageWrapper>
  );
}

function EditGroupWrapper({ groupId, onClose }: { groupId: string; onClose: () => void }) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ["device-groups", groupId],
    queryFn: () => deviceGroupsApi.get(groupId),
  });

  if (isLoading || !detail) return null;

  return <GroupModal isOpen group={detail} onClose={onClose} />;
}
