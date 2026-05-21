import { useQuery } from '@tanstack/react-query';
import {
  ListTodo,
  PlayCircle,
  AlertTriangle,
  Clock,
} from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusPie } from '@/components/analytics/StatusPie';
import { DepartmentBar } from '@/components/analytics/DepartmentBar';
import { CompletionLine } from '@/components/analytics/CompletionLine';
import { WorkloadHeatmap } from '@/components/analytics/WorkloadHeatmap';
import {
  getAnalyticsOverview,
  getWorkloadAnalytics,
  getCompletionAnalytics,
  getDelegationFlow,
} from '@/api/analytics';
import { PRIORITY_LABELS } from '@/lib/statusUtils';
import type { Priority } from '@/types';

const PRIORITY_CHART_COLORS: Record<Priority, string> = {
  LOW: '#64748b',
  MEDIUM: '#0ea5e9',
  HIGH: '#f97316',
  CRITICAL: '#ef4444',
};

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  loading,
}: {
  title: string;
  value: number | string;
  icon: React.ElementType;
  color: string;
  loading: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            {loading ? (
              <>
                <Skeleton className="h-4 w-24 mb-2" />
                <Skeleton className="h-8 w-16" />
              </>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">{title}</p>
                <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
              </>
            )}
          </div>
          <div className={`rounded-lg bg-muted p-3 ${color}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: getAnalyticsOverview,
  });

  const { data: workload, isLoading: workloadLoading } = useQuery({
    queryKey: ['analytics', 'workload'],
    queryFn: getWorkloadAnalytics,
  });

  const { data: completion, isLoading: completionLoading } = useQuery({
    queryKey: ['analytics', 'completion'],
    queryFn: () => getCompletionAnalytics('week'),
  });

  const { data: delegation } = useQuery({
    queryKey: ['analytics', 'delegation'],
    queryFn: getDelegationFlow,
  });

  const priorityData = overview?.by_priority?.map((p) => ({
    name: PRIORITY_LABELS[p.priority],
    value: p.count,
    color: PRIORITY_CHART_COLORS[p.priority],
  })) ?? [];

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Всего задач" value={overview?.total_tasks ?? 0} icon={ListTodo} color="text-primary" loading={overviewLoading} />
        <StatCard title="В работе" value={overview?.in_progress ?? 0} icon={PlayCircle} color="text-blue-600" loading={overviewLoading} />
        <StatCard title="Просрочено" value={overview?.overdue ?? 0} icon={Clock} color="text-rose-600" loading={overviewLoading} />
        <StatCard title="В зоне риска" value={overview?.at_risk ?? 0} icon={AlertTriangle} color="text-amber-600" loading={overviewLoading} />
      </div>

      {/* Pie charts row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {overviewLoading ? (
          <>
            <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
            <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
          </>
        ) : (
          <>
            <StatusPie data={overview?.by_status ?? []} />
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Распределение по приоритетам</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={priorityData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={3}
                      dataKey="value"
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      labelLine={false}
                    >
                      {priorityData.map((entry, index) => (
                        <Cell key={index} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number) => [`${value} задач`, '']}
                      contentStyle={{
                        backgroundColor: 'hsl(var(--card))',
                        border: '1px solid hsl(var(--border))',
                        borderRadius: '8px',
                      }}
                    />
                    <Legend formatter={(value) => <span className="text-xs">{value}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Department bar */}
      {overviewLoading ? (
        <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
      ) : (
        <DepartmentBar data={overview?.by_department ?? []} />
      )}

      {/* Completion line */}
      {completionLoading ? (
        <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
      ) : (
        <CompletionLine data={completion ?? []} />
      )}

      {/* Workload */}
      {workloadLoading ? (
        <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
      ) : (
        <WorkloadHeatmap data={workload ?? []} />
      )}

      {/* Delegation flow - simplified as list */}
      {delegation && delegation.links.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Потоки делегирования</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {delegation.links
                .sort((a, b) => b.value - a.value)
                .slice(0, 15)
                .map((link, i) => {
                  const source = delegation.nodes.find((n) => n.id === link.source);
                  const target = delegation.nodes.find((n) => n.id === link.target);
                  return (
                    <div key={i} className="flex items-center gap-2 sm:gap-3 text-sm flex-wrap">
                      <span className="font-medium">{source?.name ?? link.source}</span>
                      <span className="text-muted-foreground">создал</span>
                      <span className="font-bold text-primary">{link.value}</span>
                      <span className="text-muted-foreground">задач для</span>
                      <span className="font-medium">{target?.name ?? link.target}</span>
                    </div>
                  );
                })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
