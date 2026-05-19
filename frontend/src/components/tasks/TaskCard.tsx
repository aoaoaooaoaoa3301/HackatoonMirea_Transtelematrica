import { Link } from 'react-router-dom';
import { Target, Mountain, ListTodo, CheckSquare, Calendar } from 'lucide-react';
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
} from '@/lib/statusUtils';
import { formatDateShort } from '@/lib/dateUtils';
import type { Task, TaskType } from '@/types';

const typeIcons: Record<TaskType, React.ElementType> = {
  GOAL: Target,
  EPIC: Mountain,
  TASK: ListTodo,
  SUBTASK: CheckSquare,
};

interface TaskCardProps {
  task: Task;
  compact?: boolean;
}

export function TaskCard({ task, compact = false }: TaskCardProps) {
  const TypeIcon = typeIcons[task.type];
  const statusColor = STATUS_COLORS[task.status];
  const priorityColor = PRIORITY_COLORS[task.priority];

  const initials = task.assignee?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  if (compact) {
    return (
      <Link to={`/tasks/${task.id}`} className="block">
        <div className="flex items-center gap-3 rounded-md border p-3 hover:bg-accent/50 transition-colors">
          <TypeIcon className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="flex-1 text-sm truncate">{task.title}</span>
          <Badge className={`${statusColor.text} ${statusColor.bg} border-0 text-[11px]`}>
            {STATUS_LABELS[task.status]}
          </Badge>
          <Badge className={`${priorityColor.text} ${priorityColor.bg} border-0 text-[11px]`}>
            {PRIORITY_LABELS[task.priority]}
          </Badge>
          {task.assignee && (
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
      <Card className="hover:shadow-md transition-shadow cursor-pointer group">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-muted p-2 shrink-0 group-hover:bg-primary/10 transition-colors">
              <TypeIcon className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="text-sm font-medium leading-tight line-clamp-2">{task.title}</h3>
              </div>

              <div className="flex flex-wrap items-center gap-1.5 mb-3">
                <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                  {TASK_TYPE_LABELS[task.type]}
                </Badge>
                <Badge className={`${statusColor.text} ${statusColor.bg} border-0 text-[10px] px-1.5 py-0`}>
                  {STATUS_LABELS[task.status]}
                </Badge>
                <Badge className={`${priorityColor.text} ${priorityColor.bg} border-0 text-[10px] px-1.5 py-0`}>
                  {PRIORITY_LABELS[task.priority]}
                </Badge>
              </div>

              {task.type !== 'SUBTASK' && (
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[11px] text-muted-foreground">Прогресс</span>
                    <span className="text-[11px] text-muted-foreground">{task.progress}%</span>
                  </div>
                  <Progress value={task.progress} className="h-1.5" />
                </div>
              )}

              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {task.assignee && (
                    <div className="flex items-center gap-1.5">
                      <Avatar className="h-5 w-5">
                        <AvatarFallback className="text-[9px] bg-primary/10">{initials}</AvatarFallback>
                      </Avatar>
                      <span className="text-[11px] text-muted-foreground truncate max-w-[100px]">
                        {task.assignee.full_name}
                      </span>
                    </div>
                  )}
                </div>
                {task.due_date && (
                  <div className="flex items-center gap-1 text-muted-foreground">
                    <Calendar className="h-3 w-3" />
                    <span className="text-[11px]">{formatDateShort(task.due_date)}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
