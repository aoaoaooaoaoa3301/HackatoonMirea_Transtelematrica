import apiClient from './client';
import type {
  AnalyticsOverview,
  WorkloadEntry,
  CompletionEntry,
  DelegationFlow,
} from '@/types';

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const res = await apiClient.get<AnalyticsOverview>('/analytics/overview');
  return res.data;
}

export async function getWorkloadAnalytics(): Promise<WorkloadEntry[]> {
  const res = await apiClient.get<WorkloadEntry[]>('/analytics/workload');
  return res.data;
}

export async function getCompletionAnalytics(period: string = 'week'): Promise<CompletionEntry[]> {
  const res = await apiClient.get<CompletionEntry[]>('/analytics/completion', {
    params: { period },
  });
  return res.data;
}

export async function getDelegationFlow(): Promise<DelegationFlow> {
  const res = await apiClient.get<DelegationFlow>('/analytics/delegation-flow');
  return res.data;
}
