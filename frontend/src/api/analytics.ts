import apiClient from './client';
import type {
  AnalyticsOverview,
  WorkloadEntry,
  CompletionEntry,
  DelegationFlow,
  Status,
  Priority,
} from '@/types';

export async function getAnalyticsOverview(): Promise<AnalyticsOverview> {
  const res = await apiClient.get('/analytics/overview');
  const d = res.data as Record<string, any>;
  const byStatus: Record<string, number> = d.by_status ?? {};
  const byPriority: Record<string, number> = d.by_priority ?? {};

  return {
    total_tasks: d.total ?? 0,
    in_progress: byStatus.IN_PROGRESS ?? 0,
    overdue: d.overdue_count ?? byStatus.OVERDUE ?? 0,
    at_risk: d.at_risk_count ?? 0,
    done: byStatus.DONE ?? 0,
    new_tasks: byStatus.NEW ?? 0,
    review: byStatus.REVIEW ?? 0,
    by_status: Object.entries(byStatus).map(([status, count]) => ({
      status: status as Status,
      count: count as number,
    })),
    by_priority: Object.entries(byPriority).map(([priority, count]) => ({
      priority: priority as Priority,
      count: count as number,
    })),
    by_department: (d.by_department ?? []).map((x: any) => {
      const total = x.count ?? 0;
      const done = x.done ?? 0;
      const overdue = x.overdue ?? 0;
      const in_progress = Math.max(0, total - done - overdue);
      return {
        department_id: x.id ?? x.department_id ?? '',
        department_name: x.name ?? x.department_name ?? '—',
        total,
        done,
        in_progress,
        overdue,
      };
    }),
  };
}

export async function getWorkloadAnalytics(): Promise<WorkloadEntry[]> {
  const res = await apiClient.get('/analytics/workload');
  return (res.data as any[]).map((u) => ({
    user_id: u.user_id,
    full_name: u.full_name,
    department: u.department_name ?? u.department ?? '—',
    open_tasks: u.open_tasks ?? 0,
    weighted_load: u.weighted_load ?? 0,
    overdue: u.overdue_count ?? u.overdue ?? 0,
    at_risk: u.at_risk_count ?? u.at_risk ?? 0,
    capacity_util: u.capacity_util ?? 0,
  }));
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
