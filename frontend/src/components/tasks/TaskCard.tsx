import { Link } from 'react-router-dom';
import { Target, Mountain, ListTodo, CheckSquare, Calendar, Flag } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Progress } from '@/components/ui/progress';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
  TASK_TYPE_LABELS,
  PERIOD_LABELS,
  isAtRisk,
  AT_RISK_STYLE,
} from '@/lib/statusUtils';
import { formatDateShort } from '@/lib/dateUtils';
import { cn } from '@/lib/utils';
import type { Task, TaskType, Priority } from '@/types';

const typeIcons: Record<TaskType, React.ElementType> = {
  GOAL: Target,
  EPIC: Mountain,
  TASK: ListTodo,
  SUBTASK: CheckSquare,
};

function getPriorityBorderClass(priority: Priority): string {
  switch (priority) {
    case 'CRITICAL':
      return 'border-t-2 border-t-rose-500';
    case 'HIGH':
      return 'border-t-2 border-t-amber-500';
    case 'MEDIUM':
      return 'border-t-2 border-t-blue-500';
    default:
      return '';
  }
}

interface TaskCardProps {
  task: Task;
  compact?: boolean;
}

export function TaskCard({ task, compact = false }: TaskCardProps) {
  const TypeIcon = typeIcons[task.type];
  const statusColor = STATUS_COLORS[task.status];
  const priorityColor = PRIORITY_COLORS[task.priority];
  const atRisk = isAtRisk(task.due_date, task.status);

  const displayStatusLabel = atRisk ? AT_RISK_STYLE.label : STATUS_LABELS[task.status];
  const displayStatusText = atRisk ? AT_RISK_STYLE.text : statusColor.text;
  const displayStatusBg = atRisk ? AT_RISK_STYLE.bg : statusColor.bg;
  const assigneeName = task.assignee_name ?? task.assignee?.full_name ?? null;
  const departmentName = task.assigned_department_name ?? task.department?.name ?? null;

  const initials = assigneeName
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const periodLabel = task.period_bucket ? PERIOD_LABELS[task.period_bucket] : null;

  if (compact) {
    return (
      <Link to={`/tasks/${task.id}`} className="block">
        <div className="flex items-center gap-3 rounded-md border p-3 hover:bg-accent/50 transition-colors">
          <TypeIcon className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="flex-1 text-sm truncate">{task.title}</span>
          <Badge className={`${displayStatusText} ${displayStatusBg} border-0 text-[11px]`}>
            {displayStatusLabel}
          </Badge>
          <Badge className={`${priorityColor.text} ${priorityColor.bg} border-0 text-[11px]`}>
            {PRIORITY_LABELS[task.priority]}
          </Badge>
          {assigneeName && (
            <Avatar className="h-6 w-6">
              <AvatarFallback className="text-[10px] bg-primary/10">{initials}</AvatarFallback>
            </Avatar>
          )}
          {task.due_date && (
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {formatDateShort(task.due_date)}
            </span>
          )}
        </div>
      </Link>
    );
  }

  return (
    <Link to={`/tasks/${task.id}`} className="block">
      <Card className={cn(
        'hover:shadow-md transition-shadow cursor-pointer group overflow-hidden h-full',
        getPriorityBorderClass(task.priority)
      )}>
        <CardContent className="flex flex-col p-4 h-full justify-between">
          <div>{/* Top row: status badge left, period badge right */}

          <div className="flex items-center justify-between mb-3">
            <Badge className={cn(
              'border-0 text-[10px] px-2 py-0.5 rounded-md font-medium',
              displayStatusText,
              displayStatusBg
            )}>
              {displayStatusLabel}
            </Badge>
            {periodLabel && (
              <Badge variant="secondary" className="text-[10px] px-2 py-0.5 rounded-md font-normal text-muted-foreground">
                {periodLabel}
              </Badge>
            )}
          </div>
          
            {/* Title */}
          <h3 className="text-sm font-semibold leading-tight line-clamp-2 mb-3">
              {task.title}
          </h3>
          </div>
          

          <div>
            {/* Progress (for non-subtasks) */}
            
              <div className="mb-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] text-muted-foreground">Прогресс</span>
                  <span className="text-[11px] text-muted-foreground">{task.progress}%</span>
                </div>
                <Progress value={task.progress} className="h-1.5" />
              </div>
            

            {/* Assignee row */}
            {assigneeName && (
              <div className="flex items-center gap-2 mb-3">
                <Avatar className="h-6 w-6">
                  <AvatarFallback className="text-[9px] bg-primary/10 text-primary">{initials}</AvatarFallback>
                </Avatar>
                <div className="flex flex-col min-w-0">
                  <span className="text-[12px] font-medium truncate">
                    {assigneeName}
                  </span>
                  {departmentName && (
                    <span className="text-[10px] text-muted-foreground truncate">
                      {departmentName}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Bottom row: priority + date */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Flag className={cn('h-3 w-3', priorityColor.text)} />
                <span className={cn('text-[11px] font-medium', priorityColor.text)}>
                  {PRIORITY_LABELS[task.priority]}
                </span>
              </div>
              {task.due_date && (
                <div className="flex items-center gap-1 text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  <span className="text-[11px]">{formatDateShort(task.due_date)}</span>
                </div>
              )}
            </div>

          </div>

        </CardContent>
      </Card>
    </Link>
  );
}
