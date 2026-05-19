import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ListTodo,
  PlayCircle,
  AlertTriangle,
  Clock,
  ArrowRight,
  Users,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusPie } from '@/components/analytics/StatusPie';
import { DepartmentBar } from '@/components/analytics/DepartmentBar';
import { DigestCard } from '@/components/ai/DigestCard';
import { RiskList } from '@/components/ai/RiskList';
import { getAnalyticsOverview, getWorkloadAnalytics } from '@/api/analytics';
import { getCapacityColor, getCapacityBgColor } from '@/lib/statusUtils';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ElementType;
  description?: string;
  color?: string;
  loading?: boolean;
}

function StatCard({ title, value, icon: Icon, description, color = 'text-primary', loading }: StatCardProps) {
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
                {description && (
                  <p className="text-xs text-muted-foreground mt-1">{description}</p>
                )}
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

export default function DashboardPage() {
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: getAnalyticsOverview,
  });

  const { data: workload, isLoading: workloadLoading } = useQuery({
    queryKey: ['analytics', 'workload'],
    queryFn: getWorkloadAnalytics,
  });

  const topWorkload = workload?.sort((a, b) => b.capacity_util - a.capacity_util).slice(0, 6);

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Всего задач"
          value={overview?.total_tasks ?? 0}
          icon={ListTodo}
          loading={overviewLoading}
        />
        <StatCard
          title="В работе"
          value={overview?.in_progress ?? 0}
          icon={PlayCircle}
          color="text-blue-600"
          loading={overviewLoading}
        />
        <StatCard
          title="Просрочено"
          value={overview?.overdue ?? 0}
          icon={Clock}
          color="text-rose-600"
          loading={overviewLoading}
        />
        <StatCard
          title="В зоне риска"
          value={overview?.at_risk ?? 0}
          icon={AlertTriangle}
          color="text-amber-600"
          loading={overviewLoading}
        />
      </div>

      {/* Charts + Digest row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {overviewLoading ? (
              <>
                <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
                <Card><CardContent className="p-6"><Skeleton className="h-64 w-full" /></CardContent></Card>
              </>
            ) : (
              <>
                <StatusPie data={overview?.by_status ?? []} />
                <DepartmentBar data={overview?.by_department ?? []} />
              </>
            )}
          </div>
        </div>
        <div>
          <DigestCard />
        </div>
      </div>

      {/* Workload + Risks row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  Загруженность команды
                </CardTitle>
                <Link to="/team">
                  <Badge variant="outline" className="cursor-pointer hover:bg-accent">
                    Все <ArrowRight className="ml-1 h-3 w-3" />
                  </Badge>
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {workloadLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <Skeleton key={i} className="h-8 w-full" />
                  ))}
                </div>
              ) : (
                <div className="space-y-3">
                  {topWorkload?.map((entry) => (
                    <div key={entry.user_id} className="flex items-center gap-3">
                      <span className="text-sm w-36 truncate">{entry.full_name}</span>
                      <div className="flex-1">
                        <Progress
                          value={Math.min(entry.capacity_util, 150)}
                          max={150}
                          className="h-2"
                          indicatorClassName={getCapacityBgColor(entry.capacity_util)}
                        />
                      </div>
                      <span className={`text-sm font-medium w-12 text-right ${getCapacityColor(entry.capacity_util)}`}>
                        {Math.round(entry.capacity_util)}%
                      </span>
                      <div className="flex gap-2 text-xs text-muted-foreground w-32">
                        <span>{entry.open_tasks} задач</span>
                        {entry.overdue > 0 && (
                          <span className="text-rose-500">{entry.overdue} просроч.</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {(!topWorkload || topWorkload.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      Нет данных о загрузке
                    </p>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
        <div>
          <RiskList limit={8} />
        </div>
      </div>
    </div>
  );
}
