import { Bot, User } from "lucide-react";
import type { ChatMessage } from "../../store/agentStore";

interface MessageBubbleProps {
  message: ChatMessage;
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
        {isUser ? <User size={16} className="text-white" /> : <Bot size={16} className="text-white" />}
      </div>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap ${
          isUser ? "bg-brand-600 text-white rounded-tr-sm" : "bg-gray-100 text-gray-900 rounded-tl-sm"
        }`}
      >
        {message.content}
      </div>
    </div>
  );
}
