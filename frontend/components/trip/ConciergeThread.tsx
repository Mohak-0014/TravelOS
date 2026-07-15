"use client";

import { motion } from "framer-motion";
import { Compass, ChevronRight, Send, Utensils, Luggage, Bus } from "lucide-react";
import type { ChatSource } from "@/lib/api";
import { Input } from "@/components/ui/Input";

export type ChatMessage = { role: "user" | "assistant"; text: string; sources?: ChatSource[] };

const SUGGESTIONS_ICONS = [Utensils, Luggage, Bus];

export function ConciergeThread({
  destinationCity,
  messages,
  input,
  onInputChange,
  onSubmit,
  loading,
  chatEndRef,
  onSuggestionClick,
}: {
  destinationCity: string;
  messages: ChatMessage[];
  input: string;
  onInputChange: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  chatEndRef: React.RefObject<HTMLDivElement>;
  onSuggestionClick: (q: string) => void;
}) {
  const suggestions = [`Best restaurants in ${destinationCity}?`, "What should I pack?", "Local transport tips"];

  return (
    <div className="flex-1 min-h-0 rounded-xl border border-accent/25 overflow-hidden flex flex-col bg-surface">
      {/* Header */}
      <div className="relative flex items-center gap-3 px-4 py-3.5 border-b border-accent/15 shrink-0 bg-accent-tint">
        <div className="relative w-8 h-8 rounded-lg bg-sunset flex items-center justify-center shrink-0">
          <Compass className="w-3.5 h-3.5 text-[#1F1206]" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-success border-2 border-accent-tint" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-ink-900">AI Concierge</p>
          <p className="text-[10px] text-success font-medium">{destinationCity} specialist</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4 scrollbar-hide">
        {messages.length === 0 && (
          <div className="flex flex-col items-center px-2 py-8">
            <div className="w-14 h-14 mb-4 rounded-full bg-accent-tint flex items-center justify-center shrink-0">
              <Compass className="w-6 h-6 text-accent" />
            </div>
            <h3 className="text-sm font-medium text-ink-900 mb-1 text-center">Your {destinationCity} Guide</h3>
            <p className="text-[11px] text-ink-400 text-center leading-relaxed mb-5 max-w-[200px]">
              Real-time advice on restaurants, hidden spots, logistics and more
            </p>
            <div className="w-full space-y-2">
              {suggestions.map((q, i) => {
                const Icon = SUGGESTIONS_ICONS[i];
                return (
                  <motion.button
                    key={q}
                    whileHover={{ x: 2 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => onSuggestionClick(q)}
                    className="w-full flex items-center gap-3 text-left px-3.5 py-2.5 rounded-lg text-xs bg-ink-100 text-ink-600 hover:bg-ink-100/70 hover:text-ink-900 transition-colors group"
                  >
                    <Icon className="w-3.5 h-3.5 shrink-0 text-ink-400" />
                    <span className="flex-1">{q}</span>
                    <ChevronRight className="w-3 h-3 text-ink-300 group-hover:text-accent transition-colors" />
                  </motion.button>
                );
              })}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 8, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ type: "spring", damping: 28, stiffness: 380 }}
          >
            {msg.role === "assistant" ? (
              <div className="flex items-start gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-sunset flex items-center justify-center shrink-0 mt-0.5">
                  <Compass className="w-3 h-3 text-[#1F1206]" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="bg-ink-100 text-ink-600 text-xs px-3.5 py-2.5 rounded-2xl rounded-tl-sm leading-relaxed">{msg.text}</div>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5">
                      {msg.sources.slice(0, 4).map((s, j) => (
                        <span key={j} className="text-[10px] bg-accent-tint text-accent px-2 py-0.5 rounded-full">
                          {s.name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex justify-end">
                <div className="bg-sunset text-[#1F1206] text-xs px-3.5 py-2.5 rounded-2xl rounded-br-sm max-w-[85%] leading-relaxed">
                  {msg.text}
                </div>
              </div>
            )}
          </motion.div>
        ))}
        {loading && (
          <div className="flex items-start gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-sunset flex items-center justify-center shrink-0">
              <Compass className="w-3 h-3 text-[#1F1206]" />
            </div>
            <div className="bg-ink-100 px-4 py-3 rounded-2xl rounded-tl-sm">
              <div className="flex gap-1.5 items-center h-3">
                {[0, 1, 2].map((i) => (
                  <motion.div
                    key={i}
                    className="w-1.5 h-1.5 bg-accent rounded-full"
                    animate={{ y: [-3, 0, -3] }}
                    transition={{ repeat: Infinity, duration: 0.9, delay: i * 0.18, ease: "easeInOut" }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-accent/15 shrink-0">
        <form onSubmit={onSubmit} className="flex gap-2 items-center">
          <Input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            disabled={loading}
            placeholder={`Ask about ${destinationCity}…`}
            className="text-xs h-10 flex-1"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="w-9 h-9 rounded-lg bg-sunset text-[#1F1206] flex items-center justify-center disabled:opacity-40 shrink-0 hover:shadow-glow transition-shadow"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}
