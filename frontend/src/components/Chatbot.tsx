"use client";

import React, { useState, useRef, useEffect } from "react";
import { motion as Motion, AnimatePresence } from "framer-motion";
import AppIcon from "@/components/AppIcon";

type Message = {
  id: string;
  sender: "user" | "bot";
  text: string;
};

const predefinedQA: Record<string, string> = {
  "Where do I see my stats?": "Your stats and exam analytics are available on your Dashboard. Look for the 'Exam Analytics History' section at the bottom.",
  "How is my resume analyzed?": "Your resume is analyzed against the target role you provide, checking for keyword presence, score breakdown across dimensions, and identifying any recruiter-visible red flags.",
  "How do I take an assessment?": "Navigate to the 'Assessments' page from the sidebar to take rule-based assessments and raise your readiness score.",
  "What is Career Aim?": "Career Aim helps you compare your current skills against your desired role to highlight major gaps and suggest a roadmap."
};

export default function Chatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { id: "1", sender: "bot", text: "Hi! I am the CELTM helper bot. How can I help you today?" }
  ]);
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSend = async (question: string) => {
    if (isSending) return;
    const outgoingHistory = messages.slice(-8).map((message) => ({
      role: message.sender === "user" ? "user" : "assistant",
      content: message.text,
    }));
    setIsSending(true);
    setMessages(prev => [...prev, { id: Date.now().toString() + "_u", sender: "user", text: question }]);

    try {
      const { apiFetch } = await import("@/lib/api");
      const res = await apiFetch<{ response: string }>("/chat", {
        method: "POST",
        body: JSON.stringify({ message: question, history: outgoingHistory })
      });
      setMessages(prev => [...prev, { id: Date.now().toString() + "_b", sender: "bot", text: res.response }]);
    } catch (error) {
      console.error(error);
      setMessages(prev => [...prev, { id: Date.now().toString() + "_b", sender: "bot", text: "The CELTM assistant could not reach the AI service. Check the backend API and AI key, then try again." }]);
    } finally {
      setIsSending(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="fixed bottom-6 right-6 h-14 w-14 rounded-full bg-primary text-white shadow-xl flex items-center justify-center hover:scale-110 transition-transform z-[120]"
      >
        <AppIcon name={isOpen ? "close" : "chat"} className="h-6 w-6" />
      </button>

      <AnimatePresence>
        {isOpen && (
          <Motion.div
            initial={{ opacity: 0, y: 30, scale: 0.95, originY: 1, originX: 1 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 30, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 300, damping: 25 }}
            className="fixed bottom-24 right-6 w-[90vw] sm:w-[450px] rounded-[24px] bg-surface border border-outline-variant/20 shadow-2xl overflow-hidden z-[120] flex flex-col h-[600px] max-h-[85vh]"
          >
            <div className="bg-primary px-4 py-3 flex items-center justify-between text-white">
              <div className="flex items-center gap-2">
                <AppIcon name="smart_toy" className="h-5 w-5" />
                <span className="font-bold">CELTM Assistant</span>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.sender === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[85%] rounded-2xl px-5 py-3 text-base leading-relaxed whitespace-pre-wrap ${msg.sender === "user" ? "bg-primary text-white rounded-tr-sm" : "bg-surface-container-high text-on-surface rounded-tl-sm"}`}>
                    {msg.text}
                  </div>
                </div>
              ))}
              {isSending && (
                <div className="flex justify-start">
                  <div className="max-w-[85%] rounded-2xl px-5 py-3 text-base leading-relaxed bg-surface-container-high text-on-surface rounded-tl-sm flex items-center gap-1.5 h-12">
                    <span className="w-2 h-2 rounded-full bg-primary animate-bounce"></span>
                    <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '150ms' }}></span>
                    <span className="w-2 h-2 rounded-full bg-primary animate-bounce" style={{ animationDelay: '300ms' }}></span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="p-3 border-t border-outline-variant/20 bg-surface-container-lowest">
              <div className="flex flex-wrap gap-2 mb-3">
                {Object.keys(predefinedQA).map((q) => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    disabled={isSending}
                    className="text-left text-sm bg-surface-container-high hover:bg-outline-variant/20 text-primary px-4 py-2 rounded-full transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const form = e.target as HTMLFormElement;
                  const input = form.elements.namedItem("message") as HTMLInputElement;
                  if (input.value.trim()) {
                    void handleSend(input.value.trim());
                    input.value = "";
                  }
                }}
                className="flex gap-2"
              >
                <input
                  name="message"
                  type="text"
                  placeholder="Ask a question..."
                  className="flex-1 rounded-full border border-outline-variant/30 bg-surface px-5 py-3 text-base outline-none focus:border-primary"
                  autoComplete="off"
                  disabled={isSending}
                />
                <button type="submit" disabled={isSending} className="flex h-12 w-12 items-center justify-center rounded-full bg-primary text-white hover:scale-105 transition-transform shrink-0 disabled:opacity-60">
                  <AppIcon name={isSending ? "sync" : "send"} className="h-5 w-5" />
                </button>
              </form>
            </div>
          </Motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
