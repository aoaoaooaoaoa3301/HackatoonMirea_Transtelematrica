import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ListTodo,
  CheckCircle2,
  PlayCircle,
  Clock,
  AlertTriangle,
  ArrowRight,
  Users,
  Sparkles,
  ChevronRight,
  AlertCircle,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusPie } from '@/components/analytics/StatusPie';
import { DepartmentBar } from '@/components/analytics/DepartmentBar';
import { getAnalyticsOverview, getWorkloadAnalytics } from '@/api/analytics';
import { getRisks, getDigest } from '@/api/ai';
import { getCapacityColor, getCapacityBgColor } from '@/lib/statusUtils';

/* ------------------------------------------------------------------ */
/*  StatCard                                                           */
/* ------------------------------------------------------------------ */

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ElementType;
  delta?: string;
  deltaColor?: 'positive' | 'negative' | 'neutral';
  iconColorClass?: string;
  iconBgClass?: string;
  loading?: boolean;
  /** When set, the whole card becomes a link (e.g. to a filtered task list). */
  to?: string;
}

function StatCard({
  title,
  value,
  icon: Icon,
  delta,
  deltaColor = 'neutral',
  iconColorClass = 'text-primary',
  iconBgClass = 'bg-primary/15',
  loading,
  to,
}: StatCardProps) {
  const deltaTextColor =
    deltaColor === 'positive'
      ? 'text-emerald-500'
      : deltaColor === 'negative'
        ? 'text-rose-500'
        : 'text-muted-foreground';

  const card = (
    <Card className={`h-full ${to ? 'transition-colors hover:border-primary/50 hover:bg-secondary/40' : ''}`}>
      <CardContent className="p-4 sm:p-5">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-9 w-9 rounded-md" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-8 w-16" />
          </div>
        ) : (
          <>
            <div className={`flex h-9 w-9 sm:h-10 sm:w-10 items-center justify-center rounded-md ${iconBgClass}`}>
              <Icon className={`h-5 w-5 ${iconColorClass}`} />
            </div>
            <p className="text-xs sm:text-sm text-muted-foreground mt-2 sm:mt-3 truncate">{title}</p>
            <p className="text-2xl sm:text-3xl font-semibold mt-0.5 sm:mt-1">{value}</p>
            {delta && (
              <p className={`text-[11px] sm:text-xs mt-0.5 sm:mt-1 ${deltaTextColor} truncate`}>{delta}</p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );

  return to && !loading ? (
    <Link to={to} className="block">
      {card}
    </Link>
  ) : (
    card
  );
}

/* ------------------------------------------------------------------ */
/*  AI Recommendation Card                                             */
/* ------------------------------------------------------------------ */

interface RecommendationCardProps {
  borderColor: string;
  iconBg: string;
  iconColor: string;
  icon: React.ElementType;
  title: string;
  description: string;
  link?: string;
}

function RecommendationCard({
  borderColor,
  iconBg,
  iconColor,
  icon: Icon,
  title,
  description,
  link,
}: RecommendationCardProps) {
  const content = (
    <div className={`flex items-start gap-3 rounded-lg border p-3 hover:bg-secondary/50 transition-colors ${borderColor}`}>
      <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${iconBg}`}>
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-tight">{title}</p>
        <p className="text-xs text-muted-foreground mt-1 line-clamp-2">{description}</p>
      </div>
      <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
    </div>
  );

  if (link) {
    return <Link to={link} className="block">{content}</Link>;
  }
  return content;
}

/* ------------------------------------------------------------------ */
/*  AI Sidebar Panel                                                   */
/* ------------------------------------------------------------------ */

function AISidebarPanel() {
  const { data: risksData, isLoading: risksLoading, isError: risksError } = useQuery({
    queryKey: ['ai', 'risks', 'all', undefined],
    queryFn: () => getRisks({ scope: 'all' }),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const { data: digestData, isLoading: digestLoading, isError: digestError } = useQuery({
    queryKey: ['ai', 'digest', 'all', undefined, 'week'],
    queryFn: () => getDigest({ scope: 'all', period: 'week' }),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  const isLoading = risksLoading || digestLoading;
  const isError = risksError && digestError;

  // Build recommendation cards from risk data
  const highRisks = risksData?.items.filter((r) => r.risk_level === 'high') ?? [];
  const medRisks = risksData?.items.filter((r) => r.risk_level === 'medium') ?? [];

  const recommendations: RecommendationCardProps[] = [];

  if (highRisks.length > 0) {
    recommendations.push({
      borderColor: 'border-l-4 border-l-rose-500',
      iconBg: 'bg-rose-500/15',
      iconColor: 'text-rose-500',
      icon: AlertTriangle,
      title: `${highRisks.length} ${highRisks.length === 1 ? 'задача требует внимания' : highRisks.length < 5 ? 'задачи требуют внимания' : 'задач требуют внимания'}`,
      description: highRisks.length > 0
        ? `Высокий риск: ${highRisks.slice(0, 2).map((r) => r.task_title).join(', ')}`
        : 'Проверьте задачи с высоким риском',
      link: highRisks.length === 1 ? `/tasks/${highRisks[0].task_id}` : '/tasks?tab=list&status=OVERDUE',
    });
  }

  if (medRisks.length > 0) {
    recommendations.push({
      borderColor: 'border-l-4 border-l-amber-500',
      iconBg: 'bg-amber-500/15',
      iconColor: 'text-amber-500',
      icon: Clock,
      title: `${medRisks.length} ${medRisks.length === 1 ? 'задача в зоне риска' : medRisks.length < 5 ? 'задачи в зоне риска' : 'задач в зоне риска'}`,
      description: medRisks.slice(0, 2).map((r) => r.task_title).join(', '),
      link: '/tasks',
    });
  }

  // Add digest as AI insight
  if (digestData?.summary) {
    recommendations.push({
      borderColor: 'border-l-4 border-l-violet-500',
      iconBg: 'bg-violet-500/15',
      iconColor: 'text-violet-500',
      icon: Sparkles,
      title: 'AI-сводка за неделю',
      description: digestData.summary,
      link: '/ai',
    });
  }

  // Add key points as individual cards if we have room
  if (digestData?.key_points && recommendations.length < 4) {
    const remaining = 4 - recommendations.length;
    digestData.key_points.slice(0, remaining).forEach((point) => {
      recommendations.push({
        borderColor: 'border-l-4 border-l-violet-500/50',
        iconBg: 'bg-violet-500/10',
        iconColor: 'text-violet-400',
        icon: Sparkles,
        title: 'Рекомендация',
        description: point,
        link: '/ai',
      });
    });
  }

  return (
    <Card className="w-full flex flex-col">
      <CardHeader className="pb-2">
        <CardTitle className="text-base flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-primary" />
          AI-рекомендации
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col flex-1">
        {isLoading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex gap-3 p-3">
                <Skeleton className="h-8 w-8 rounded-full shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3.5 w-3/4" />
                  <Skeleton className="h-2.5 w-full" />
                </div>
              </div>
            ))}
          </div>
        )}
        {isError && (
          <div className="flex items-center gap-2 text-muted-foreground text-sm py-4">
            <AlertCircle className="h-4 w-4" />
            AI-сервис временно недоступен
          </div>
        )}
        {!isLoading && !isError && recommendations.length === 0 && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            Нет рекомендаций - все под контролем
          </p>
        )}
        {!isLoading && recommendations.length > 0 && (
          <div className="space-y-2">
            {recommendations.slice(0, 4).map((rec, i) => (
              <RecommendationCard key={i} {...rec} />
            ))}
          </div>
        )}
        <div className="mt-auto pt-3">
          <Link to="/ai">
            <Button variant="ghost" size="sm" className="w-full text-primary hover:text-primary hover:bg-primary/10">
              Показать все рекомендации
              <ArrowRight className="ml-1 h-3 w-3" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/*  DashboardPage                                                      */
/* ------------------------------------------------------------------ */

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
      {/* Stat cards - 5 cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <StatCard
          title="Всего задач"
          value={overview?.total_tasks ?? 0}
          icon={ListTodo}
          delta="Все задачи"
          deltaColor="neutral"
          iconColorClass="text-primary"
          iconBgClass="bg-primary/15"
          loading={overviewLoading}
          to="/tasks?tab=list"
        />
        <StatCard
          title="Выполнено"
          value={overview?.done ?? 0}
          icon={CheckCircle2}
          delta="Готовые задачи"
          deltaColor="positive"
          iconColorClass="text-emerald-500"
          iconBgClass="bg-emerald-500/15"
          loading={overviewLoading}
          to="/tasks?tab=list&status=DONE"
        />
        <StatCard
          title="В работе"
          value={overview?.in_progress ?? 0}
          icon={PlayCircle}
          delta="Активные сейчас"
          deltaColor="neutral"
          iconColorClass="text-sky-500"
          iconBgClass="bg-sky-500/15"
          loading={overviewLoading}
          to="/tasks?tab=list&status=IN_PROGRESS"
        />
        <StatCard
          title="Просрочено"
          value={overview?.overdue ?? 0}
          icon={Clock}
          delta={overview?.overdue ? 'Требуют внимания' : 'Нет просроченных'}
          deltaColor={overview?.overdue ? 'negative' : 'positive'}
          iconColorClass="text-rose-500"
          iconBgClass="bg-rose-500/15"
          loading={overviewLoading}
          to="/tasks?tab=list&status=OVERDUE"
        />
        <StatCard
          title="В зоне риска"
          value={overview?.at_risk ?? 0}
          icon={AlertTriangle}
          delta="Дедлайн ≤ 3 дней"
          deltaColor="neutral"
          iconColorClass="text-violet-500"
          iconBgClass="bg-violet-500/15"
          loading={overviewLoading}
          to="/tasks?tab=list"
        />
      </div>

      {/* Charts + AI sidebar row */}
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
        <div className="flex">
          <AISidebarPanel />
        </div>
      </div>

      {/* Workload row */}
      <div className="grid grid-cols-1 gap-6">
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
                  <Link
                    key={entry.user_id}
                    to={`/team?user=${entry.user_id}`}
                    className="flex items-center gap-2 sm:gap-3 flex-wrap sm:flex-nowrap rounded-md px-2 -mx-2 py-1 hover:bg-secondary/50 transition-colors"
                    title="Открыть карточку сотрудника"
                  >
                    <span className="text-sm w-full sm:w-36 truncate">{entry.full_name}</span>
                    <div className="flex-1 min-w-0">
                      <Progress
                        value={Math.min(entry.capacity_util, 150)}
                        max={150}
                        className="h-2"
                        indicatorClassName={getCapacityBgColor(entry.capacity_util)}
                      />
                    </div>
                    <span className={`text-sm font-medium w-12 text-right shrink-0 ${getCapacityColor(entry.capacity_util)}`}>
                      {Math.round(entry.capacity_util)}%
                    </span>
                    <div className="hidden sm:flex gap-2 text-xs text-muted-foreground w-32 shrink-0">
                      <span>{entry.open_tasks} задач</span>
                      {entry.overdue > 0 && (
                        <span className="text-rose-500">{entry.overdue} просроч.</span>
                      )}
                    </div>
                  </Link>
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
    </div>
  );
}
