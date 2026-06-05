"use client";

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";

interface ChatMessage {
  id: string;
  sender: "user" | "ai";
  text: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputVal, setInputVal] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Scroll to bottom on updates
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  const quickQuestions = [
    {
      id: "q1",
      label: "Sotuv ko'rsatkichlari",
      text: "Bugungi sotuv ko'rsatkichlarini ko'rsating. Qancha qo'ng'iroq tahlil qilindi?"
    },
    {
      id: "q2",
      label: "Eng yaxshi menejer",
      text: "Shu hafta eng yaxshi natija ko'rsatgan menejer kim? Uning ko'rsatkichlari qanday?"
    },
    {
      id: "q3",
      label: "Qo'ng'iroq tahlili",
      text: "Oxirgi qo'ng'iroqlarni tahlil qiling. Qaysi qo'ng'iroqlarda zaiflik aniqlandi?"
    },
    {
      id: "q4",
      label: "Pipeline holati",
      text: "Hozirgi pipeline holati qanday? Qaysi bosqichda qancha bitim bor?"
    }
  ];

  const handleSend = (text: string) => {
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: "user",
      text
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputVal("");
    setIsTyping(true);

    // AI Simulated responses based on keyword/questions matched
    let responseText = "Kechirasiz, ushbu mavzu bo'yicha menda batafsil ma'lumot yo'q. Iltimos, sotuv ko'rsatkichlari, menejerlar faolligi yoki oxirgi qo'ng'iroqlar haqida so'rang.";

    const query = text.toLowerCase();
    if (query.includes("ko'rsatkich") || query.includes("korsatkich") || query.includes("bugungi")) {
      responseText = "Bugungi faoliyat bo'yicha scored (baholangan) qo'ng'iroqlar yo'q (obuna holati muzlatilgan). Ammo oxirgi faol kunda jami 12 ta qo'ng'iroq yozib olingan, shundan 8 tasi muvaffaqiyatli bog'langan, umumiy suhbat vaqti 24 daqiqa.";
    } else if (query.includes("menejer") || query.includes("yaxshi")) {
      responseText = "Shu haftada eng yaxshi natija ko'rsatgan menejer - Baxtiyorjon Gaziyev. Uning o'rtacha suhbat sifati 68% ballni tashkil qiladi, ammo e'tirozlar bilan ishlash (B1-B3) bosqichida zaifliklar bor.";
    } else if (query.includes("tahlili") || query.includes("zaiflik")) {
      responseText = "Oxirgi tahlil qilingan qo'ng'iroqlardan 'Avtokontakt MCHJ' suhbatida suhbat sifati 78% (yaxshi) baholandi, ammo 'Logotip ishlab chiqish' loyihasi bo'yicha chiquvchi muzokarada sifat ko'rsatkichi 45% gacha tushib ketgan.";
    } else if (query.includes("pipeline") || query.includes("bosqichda")) {
      responseText = "Hozirgi pipeline holatida jami 85 ta faol bitim mavjud. Ulardan 12 tasi 'Yopilishga yaqin leadlar' bosqichida, qolgan 73 tasi esa 'Yangi so'rov' va 'Brifing' bosqichlarida joylashgan.";
    }

    setTimeout(() => {
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          sender: "ai",
          text: responseText
        }
      ]);
    }, 1200);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-bg">
      {/* Standalone Chat Header */}
      <header className="flex h-16 w-full shrink-0 items-center justify-between border-b border-border bg-bg-card px-6">
        <Link href="/dashboards/home" className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand font-display text-lg font-bold text-white shadow-lg">
            M
          </div>
          <span className="font-display text-lg font-bold text-text tracking-wide">Metasell Chat</span>
        </Link>

        <Link
          href="/dashboards/home"
          className="rounded-xl border border-border bg-bg px-4 py-2 text-xs font-semibold text-text-muted hover:text-brand hover:border-brand transition-colors"
        >
          Dashboards &rarr;
        </Link>
      </header>

      {/* Main Panel layout */}
      <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center">
        <div className="w-full max-w-2xl flex-1 flex flex-col justify-between">
          
          {/* Welcome Screen or Message list */}
          {messages.length === 0 ? (
            <div className="space-y-8 my-auto text-center py-8">
              <div className="space-y-3">
                <h1 className="text-3xl font-bold tracking-tight">
                  <span className="text-brand">Salom, Baxtiyorjon.</span>
                  <br />
                  <span className="text-text-muted text-2xl font-semibold">Bugun sizga qanday yordam bera olaman?</span>
                </h1>
                <p className="text-xs text-text-muted max-w-md mx-auto">
                  AI-Yordamchi orqali qo&apos;ng&apos;iroqlar tahlili, sotuv menejerlari ko&apos;rsatkichlari yoki pipeline holatini tezda bilib oling.
                </p>
              </div>

              {/* Quick questions grid */}
              <div className="grid sm:grid-cols-2 gap-3 max-w-xl mx-auto">
                {quickQuestions.map((q) => (
                  <button
                    key={q.id}
                    onClick={() => handleSend(q.text)}
                    className="rounded-2xl border border-border bg-bg-card p-4 text-left transition-all hover:border-brand hover:shadow-lg hover:shadow-brand/5 hover:translate-y-[-2px] group cursor-pointer focus:outline-none"
                  >
                    <div className="text-xs font-bold text-brand">{q.label}</div>
                    <div className="text-[10px] text-text-muted mt-1 leading-relaxed line-clamp-2">
                      {q.text}
                    </div>
                    <span className="text-brand text-xs font-bold mt-2 inline-block opacity-0 group-hover:opacity-100 transition-opacity">
                      So&apos;rash &rarr;
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Chat feed log */
            <div className="space-y-4 py-4 flex-1">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`flex gap-3 max-w-[80%] ${
                    m.sender === "user" ? "ml-auto flex-row-reverse" : "mr-auto"
                  }`}
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-brand text-[10px] font-bold text-white uppercase shadow-md shadow-brand/10">
                    {m.sender === "user" ? "U" : "AI"}
                  </div>

                  <div
                    className={`rounded-2xl p-3.5 text-xs leading-relaxed ${
                      m.sender === "user"
                        ? "bg-brand text-white shadow-md shadow-brand/10"
                        : "bg-bg-card text-text border border-border shadow-sm"
                    }`}
                  >
                    {m.text}
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {isTyping && (
                <div className="flex gap-3 max-w-[80%] mr-auto items-center">
                  <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-brand text-[10px] font-bold text-white shadow-md">
                    AI
                  </div>
                  <div className="rounded-2xl p-3 bg-bg-card text-text border border-border shadow-sm text-xs font-semibold animate-pulse">
                    Javob yozilmoqda...
                  </div>
                </div>
              )}
              <div ref={scrollRef}></div>
            </div>
          )}

          {/* Bottom input form */}
          <div className="mt-4 border-t border-border pt-4 bg-bg sticky bottom-0 z-10 pb-4">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend(inputVal);
              }}
              className="flex gap-2 bg-bg-card rounded-2xl border border-border p-2 focus-within:border-brand-hover focus-within:ring-2 focus-within:ring-brand/10 transition-all shadow-sm"
            >
              <input
                type="text"
                placeholder="Xabar yozing..."
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                className="flex-1 bg-transparent px-3 py-2 text-xs text-text focus:outline-none"
              />
              <button
                type="submit"
                disabled={!inputVal.trim()}
                className="rounded-xl bg-brand px-4 py-2 text-xs font-semibold text-white hover:bg-brand-hover disabled:opacity-50 transition-colors shadow-md shadow-brand/10 cursor-pointer"
              >
                Yuborish
              </button>
            </form>
          </div>

        </div>
      </div>
    </div>
  );
}
