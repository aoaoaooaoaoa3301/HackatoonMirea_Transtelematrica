import { create } from 'zustand';
import type { User } from '@/types';
import { getStoredToken, setStoredToken, removeStoredToken } from '@/lib/auth';

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: getStoredToken(),
  user: null,
  setAuth: (token, user) => {
    setStoredToken(token);
    set({ token, user });
  },
  setUser: (user) => set({ user }),
  logout: () => {
    removeStoredToken();
    set({ token: null, user: null });
  },
  isAuthenticated: () => !!get().token,
}));
