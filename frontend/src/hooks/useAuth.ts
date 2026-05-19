import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/authStore';
import { getMe } from '@/api/auth';

export function useAuth() {
  const { token, user, setUser, logout } = useAuthStore();

  const { data, isLoading, error } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: getMe,
    enabled: !!token && !user,
    retry: false,
  });

  useEffect(() => {
    if (data) {
      setUser(data);
    }
  }, [data, setUser]);

  useEffect(() => {
    if (error) {
      logout();
    }
  }, [error, logout]);

  return {
    user: user ?? data ?? null,
    isLoading: !!token && !user && isLoading,
    isAuthenticated: !!token,
    logout,
  };
}
