import apiClient from './client';
import type { Department, DepartmentCreatePayload, DepartmentUpdatePayload } from '@/types';

export async function getDepartments(): Promise<Department[]> {
  const res = await apiClient.get<Department[]>('/departments');
  return res.data;
}

export async function createDepartment(payload: DepartmentCreatePayload): Promise<Department> {
  const res = await apiClient.post<Department>('/departments', payload);
  return res.data;
}

export async function updateDepartment(id: string, payload: DepartmentUpdatePayload): Promise<Department> {
  const res = await apiClient.patch<Department>(`/departments/${id}`, payload);
  return res.data;
}
