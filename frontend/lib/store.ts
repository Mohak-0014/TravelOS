"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { UserOut } from "./api";

interface AuthState {
  token: string | null;
  user: UserOut | null;
  _hasHydrated: boolean;
  setAuth: (token: string, user: UserOut) => void;
  clearAuth: () => void;
  logout: () => void;
  setHasHydrated: (v: boolean) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      _hasHydrated: false,
      setAuth: (token, user) => set({ token, user }),
      clearAuth: () => set({ token: null, user: null }),
      logout: () => set({ token: null, user: null }),
      setHasHydrated: (v) => set({ _hasHydrated: v }),
    }),
    {
      name: "auth-store",
      partialize: (state) => ({ token: state.token, user: state.user }),
      onRehydrateStorage: () => (state) => {
        state?.setHasHydrated(true);
      },
    },
  ),
);
