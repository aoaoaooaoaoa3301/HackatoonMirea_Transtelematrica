import apiClient from './client';
import type { User, UserWorkload, Role } from '@/types';

export async function getUsers(params?: { department_id?: string; role?: Role }): Promise<User[]> {
  const res = await apiClient.get<User[]>('/users', { params });
  return res.data;
}

export async function getUserWorkload(userId: string): Promise<UserWorkload> {
  const res = await apiClient.get<UserWorkload>(`/users/${userId}/workload`);
  return res.data;
}
