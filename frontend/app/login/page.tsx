"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Compass, Mail, Lock, User, ArrowRight, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Token, UserOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import dynamic from "next/dynamic";

const StarField = dynamic(() => import("@/components/3d/StarField"), { ssr: false });

const TAGLINES = [
  "Gets smarter every trip.",
  "Remembers what you love.",
  "Plans so you don't have to.",
  "Your AI travel brain.",
];

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const tagline = TAGLINES[Math.floor(Date.now() / 5000) % TAGLINES.length];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "register") {
        await api.post("/api/v1/auth/register", { email, password, full_name: fullName });
      }
      const tokenData = await api.post<Token>("/api/v1/auth/login", { email, password });
      const user = await api.get<UserOut>("/api/v1/auth/me", undefined, tokenData.access_token);
      setAuth(tokenData.access_token, user);
      router.push(mode === "register" ? "/onboarding" : "/trips");
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | null;
        setError(detail?.message ?? `Error ${err.status}`);
      } else {
        setError("Something went wrong. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-space-900">
      {/* 3D starfield background */}
      <StarField />

      {/* Gradient blobs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-electric-500/10 blur-3xl animate-float-slow" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-purple-600/10 blur-3xl animate-float-medium" />
        <div className="absolute top-1/2 left-1/4 w-64 h-64 rounded-full bg-gold/5 blur-3xl" />
      </div>

      {/* Center card */}
      <motion.div
        initial={{ opacity: 0, y: 32, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-sm mx-4"
      >
        {/* Logo + brand */}
        <div className="text-center mb-8">
          <motion.div
            animate={{ rotate: [0, 5, -5, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
            className="inline-flex w-14 h-14 rounded-2xl bg-electric-gradient items-center justify-center shadow-electric mb-4"
          >
            <Compass className="w-7 h-7 text-white" />
          </motion.div>
          <h1 className="text-2xl font-bold gradient-text mb-1">TravelOS</h1>
          <p className="text-sm text-slate-500">{tagline}</p>
        </div>

        {/* Glass card */}
        <div className="glass-card p-7">
          {/* Mode toggle */}
          <div className="flex rounded-xl bg-space-800/60 p-1 mb-6">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => { setMode(m); setError(null); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                  mode === m
                    ? "bg-electric-500 text-white shadow-electric-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                {m === "login" ? "Sign In" : "Register"}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <AnimatePresence mode="wait">
              {mode === "register" && (
                <motion.div
                  key="name"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.25 }}
                >
                  <div className="relative">
                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
                    <input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="Full name"
                      className="input-dark pl-10"
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="relative">
              <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                className="input-dark pl-10"
              />
            </div>

            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 pointer-events-none" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="input-dark pl-10"
              />
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="text-sm text-coral-400 bg-coral-500/10 border border-coral-500/20 rounded-xl px-4 py-3"
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>

            <motion.button
              type="submit"
              disabled={loading}
              whileTap={{ scale: 0.98 }}
              className="btn-primary flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  {mode === "login" ? "Sign in" : "Create account"}
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </motion.button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-600 mt-4">
          The travel planning system that remembers you.
        </p>
      </motion.div>
    </div>
  );
}
