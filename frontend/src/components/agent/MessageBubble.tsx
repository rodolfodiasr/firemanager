import { Bot, User } from "lucide-react";
import type { ChatMessage, TableData } from "../../store/agentStore";

interface MessageBubbleProps {
  message: ChatMessage;
}

function ResultTable({ tableData }: { tableData: TableData }) {
  return (
    <div className="mt-2 overflow-x-auto rounded-lg border border-gray-300">
      <table className="min-w-full text-xs">
        <thead className="bg-gray-200">
          <tr>
            {tableData.columns.map((col) => (
              <th
                key={col.key}
                className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap"
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tableData.rows.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
              {tableData.columns.map((col) => {
                const val = row[col.key];
                if (col.key === "enabled") {
                  if (val === null || val === undefined) {
                    return (
                      <td key={col.key} className="px-3 py-2">
                        <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">—</span>
                      </td>
                    );
                  }
                  return (
                    <td key={col.key} className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          val ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                        }`}
                      >
                        {val ? "Ativo" : "Inativo"}
                      </span>
                    </td>
                  );
                }
                if (col.key === "success") {
                  return (
                    <td key={col.key} className="px-3 py-2">
                      <span
                        className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          val ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                        }`}
                      >
                        {val ? "OK" : "Erro"}
                      </span>
                    </td>
                  );
                }
                if (col.key === "action") {
                  const action = String(val ?? "").toLowerCase();
                  const color =
                    action === "allow" || action === "accept"
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700";
                  return (
                    <td key={col.key} className="px-3 py-2">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${color}`}>
                        {String(val ?? "—")}
                      </span>
                    </td>
                  );
                }
                return (
                  <td
                    key={col.key}
                    className="px-3 py-2 text-gray-800 max-w-[160px] truncate"
                    title={String(val ?? "")}
                  >
                    {String(val ?? "—")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex-shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
          isUser ? "bg-brand-600" : "bg-gray-700"
        }`}
      >
        {isUser ? (
          <User size={16} className="text-white" />
        ) : (
          <Bot size={16} className="text-white" />
        )}
      </div>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
          isUser
            ? "bg-brand-600 text-white rounded-tr-sm"
            : "bg-gray-100 text-gray-900 rounded-tl-sm"
        }`}
      >
        {message.content}
        {message.tableData && <ResultTable tableData={message.tableData} />}
      </div>
    </div>
  );
}
