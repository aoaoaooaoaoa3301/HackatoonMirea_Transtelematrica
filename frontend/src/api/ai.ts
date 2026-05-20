import apiClient from './client';
import type {
  AIDigest,
  AIRisksResponse,
  AIOverloadEntry,
  AIParsedTask,
  AIAssigneeCandidate,
  AIGoalSummary,
} from '@/types';

export async function getDigest(params: {
  scope: string;
  id?: string;
  period: string;
}): Promise<AIDigest> {
  const res = await apiClient.post<AIDigest>('/ai/digest', params);
  return res.data;
}

export async function getRisks(params: {
  scope: string;
  id?: string;
}): Promise<AIRisksResponse> {
  const res = await apiClient.post('/ai/risks', params);
  const raw = (res.data?.items ?? []) as any[];
  const items = raw.map((it) => ({
    task_id: it.task_id,
    task_title: it.task_title ?? it.title ?? '',
    risk_level: (it.risk_level === 'med' ? 'medium' : it.risk_level) as 'high' | 'medium',
    reason: it.reason ?? '',
  }));
  return { items };
}

export async function getOverload(): Promise<{ items: AIOverloadEntry[] }> {
  const res = await apiClient.post<{ items: AIOverloadEntry[] }>('/ai/overload');
  return res.data;
}

export async function parseTask(text: string): Promise<AIParsedTask> {
  const res = await apiClient.post<AIParsedTask>('/ai/parse-task', { text });
  return res.data;
}

export async function suggestAssignee(params: {
  title: string;
  description?: string;
  department_id?: string;
  priority?: string;
  due_date?: string;
}): Promise<{ candidates: AIAssigneeCandidate[] }> {
  const res = await apiClient.post<{ candidates: AIAssigneeCandidate[] }>(
    '/ai/suggest-assignee',
    params
  );
  return res.data;
}

export async function chat(params: {
  message: string;
  context?: { task_id?: string; department_id?: string };
  history?: Array<{ role: 'user' | 'assistant'; content: string }>;
}): Promise<{ reply: string }> {
  const res = await apiClient.post<{ reply: string }>('/ai/chat', params);
  return res.data;
}

export async function getGoalSummary(goalId: string): Promise<AIGoalSummary> {
  const res = await apiClient.post<AIGoalSummary>('/ai/goal-summary', { goal_id: goalId });
  return res.data;
}
