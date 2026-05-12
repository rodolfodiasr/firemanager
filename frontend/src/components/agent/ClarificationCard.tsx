import { useState } from "react";
import { HelpCircle, Send } from "lucide-react";
import type { ClarificationQuestion } from "../../store/agentStore";

interface ClarificationCardProps {
  questions: ClarificationQuestion[];
  onSubmit: (answers: { id: string; answer: string }[]) => void;
  loading: boolean;
}

export function ClarificationCard({ questions, onSubmit, loading }: ClarificationCardProps) {
  const [answers, setAnswers] = useState<Record<string, string>>(
    Object.fromEntries(questions.map((q) => [q.id, ""]))
  );

  const allAnswered = questions.every((q) => answers[q.id]?.trim());

  const handleSubmit = () => {
    if (!allAnswered || loading) return;
    onSubmit(questions.map((q) => ({ id: q.id, answer: answers[q.id].trim() })));
  };

  return (
    <div className="mx-4 mb-3 rounded-xl border border-blue-200 bg-blue-50 p-4">
      <div className="flex items-center gap-2 mb-3">
        <HelpCircle size={16} className="text-blue-600 shrink-0" />
        <p className="text-sm font-semibold text-blue-800">
          O agente precisa de mais informações
        </p>
      </div>

      <div className="space-y-3">
        {questions.map((q) => (
          <div key={q.id}>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              {q.question}
            </label>

            {q.options && q.options.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {q.options.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setAnswers((prev) => ({ ...prev, [q.id]: opt }))}
                    className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
                      answers[q.id] === opt
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : (
              <input
                type="text"
                value={answers[q.id] ?? ""}
                onChange={(e) =>
                  setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter" && allAnswered) handleSubmit();
                }}
                placeholder="Digite sua resposta..."
                className="w-full text-sm border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
            )}
          </div>
        ))}
      </div>

      <button
        onClick={handleSubmit}
        disabled={!allAnswered || loading}
        className="mt-3 w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg px-4 py-2 transition-colors"
      >
        <Send size={14} />
        Enviar respostas
      </button>
    </div>
  );
}
