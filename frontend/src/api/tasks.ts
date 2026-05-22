import apiClient from './client';
import type {
  Task,
  TaskDetail,
  TaskComment,
  TaskFilters,
  CreateTaskPayload,
  UpdateTaskPayload,
} from '@/types';

export async function getTasks(filters?: TaskFilters): Promise<Task[]> {
  const params: Record<string, string> = {};
  if (filters) {
    if (filters.type?.length) params.type = filters.type.join(',');
    if (filters.status?.length) params.status = filters.status.join(',');
    if (filters.priority?.length) params.priority = filters.priority.join(',');
    if (filters.department_id) params.department_id = filters.department_id;
    if (filters.assignee_id) params.assignee_id = filters.assignee_id;
    if (filters.q) params.q = filters.q;
    if (filters.due_before) params.due_before = filters.due_before;
    if (filters.due_after) params.due_after = filters.due_after;
    if (filters.parent_id) params.parent_id = filters.parent_id;
  }
  const res = await apiClient.get<Task[]>('/tasks', { params });
  return res.data;
}

export async function getTask(id: string): Promise<TaskDetail> {
  const res = await apiClient.get<TaskDetail>(`/tasks/${id}`);
  return res.data;
}

export async function createTask(data: CreateTaskPayload): Promise<Task> {
  const res = await apiClient.post<Task>('/tasks', data);
  return res.data;
}

export async function updateTask(id: string, data: UpdateTaskPayload): Promise<Task> {
  const res = await apiClient.patch<Task>(`/tasks/${id}`, data);
  return res.data;
}

export async function deleteTask(id: string): Promise<void> {
  await apiClient.delete(`/tasks/${id}`);
}

export async function addComment(taskId: string, body: string): Promise<TaskComment> {
  const res = await apiClient.post<TaskComment>(`/tasks/${taskId}/comments`, { body });
  return res.data;
}

export async function updateComment(taskId: string, commentId: string, body: string): Promise<TaskComment> {
  const res = await apiClient.patch<TaskComment>(`/tasks/${taskId}/comments/${commentId}`, { body });
  return res.data;
}

export async function deleteComment(taskId: string, commentId: string): Promise<void> {
  await apiClient.delete(`/tasks/${taskId}/comments/${commentId}`);
}

export async function getTaskTree(rootId?: string): Promise<Task[]> {
  const params: Record<string, string> = {};
  if (rootId) params.root_id = rootId;
  const res = await apiClient.get<Task[]>('/tasks/tree', { params });
  return res.data;
}
