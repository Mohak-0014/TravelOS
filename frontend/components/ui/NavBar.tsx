"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Compass, Map, User, LogOut, Sparkles, Menu, X } from "lucide-react";
import { useAuthStore } from "@/lib/store";
import { Button } from "./Button";

const navItems = [
  { href: "/trips", label: "My Trips", icon: Map },
  { href: "/profile", label: "Travel DNA", icon: User },
];

export default function NavBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [mobileOpen, setMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  return (
    <>
      <motion.header
        initial={{ y: -60, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="fixed top-0 left-0 right-0 z-50 bg-paper/75 backdrop-blur-xl border-b border-ink-900/10"
      >
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          {/* Logo */}
          <Link href="/trips" className="flex items-center gap-2 group">
            <div className="w-7 h-7 rounded-lg bg-sunset flex items-center justify-center">
              <Compass className="w-4 h-4 text-[#1F1206]" />
            </div>
            <span className="font-display font-medium text-base tracking-wide text-ink-900">TravelOS</span>
          </Link>

          {/* Desktop nav items */}
          <nav className="hidden sm:flex items-center gap-1">
            {navItems.map(({ href, label, icon: Icon }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors duration-150 ${
                    active ? "bg-accent-tint text-accent" : "text-ink-400 hover:text-ink-900 hover:bg-ink-900/5"
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {label}
                </Link>
              );
            })}
          </nav>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <Link href="/trips/new">
              <Button size="sm" iconLeft={Sparkles}>
                <span className="hidden sm:inline">Plan Trip</span>
              </Button>
            </Link>
            <span className="hidden sm:block text-xs text-ink-400">{user?.email?.split("@")[0]}</span>
            <button
              onClick={handleLogout}
              className="hidden sm:flex p-1.5 rounded-lg text-ink-400 hover:text-danger hover:bg-ink-900/5 transition-colors"
              title="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>

            {/* Hamburger — mobile only */}
            <button
              onClick={() => setMobileOpen((v) => !v)}
              className="sm:hidden p-1.5 rounded-lg text-ink-400 hover:text-ink-900 hover:bg-ink-900/5 transition-colors"
              aria-label="Open menu"
            >
              {mobileOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </motion.header>

      {/* Mobile drawer overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/55 backdrop-blur-sm sm:hidden"
              onClick={() => setMobileOpen(false)}
            />

            <motion.div
              key="drawer"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", damping: 28, stiffness: 300 }}
              className="fixed top-0 right-0 h-full w-64 z-50 bg-surface border-l border-ink-900/10 shadow-overlay flex flex-col pt-16 sm:hidden"
            >
              <nav className="px-4 py-4 space-y-1">
                {navItems.map(({ href, label, icon: Icon }) => {
                  const active = pathname.startsWith(href);
                  return (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setMobileOpen(false)}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-colors duration-150 ${
                        active ? "bg-accent-tint text-accent" : "text-ink-400 hover:text-ink-900 hover:bg-ink-900/5"
                      }`}
                    >
                      <Icon className="w-4 h-4 shrink-0" />
                      {label}
                    </Link>
                  );
                })}
              </nav>

              <div className="mt-auto px-4 py-6 border-t border-ink-900/10 space-y-3">
                <p className="text-xs text-ink-400 truncate">{user?.email}</p>
                <button
                  onClick={() => {
                    setMobileOpen(false);
                    handleLogout();
                  }}
                  className="flex items-center gap-2 text-sm text-ink-400 hover:text-danger transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Sign out
                </button>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
