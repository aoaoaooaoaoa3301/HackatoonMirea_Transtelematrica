import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight, ChevronDown, Target, Mountain, ListTodo, CheckSquare } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
} from '@/lib/statusUtils';
import { formatDateShort } from '@/lib/dateUtils';
import type { Task, TaskType } from '@/types';

const typeIcons: Record<TaskType, React.ElementType> = {
  GOAL: Target,
  EPIC: Mountain,
  TASK: ListTodo,
  SUBTASK: CheckSquare,
};

const healthColor = (progress: number, status: string) => {
  if (status === 'DONE') return 'bg-emerald-500';
  if (status === 'OVERDUE') return 'bg-rose-500';
  if (progress >= 70) return 'bg-emerald-500';
  if (progress >= 40) return 'bg-amber-500';
  return 'bg-rose-500';
};

interface TaskTreeNodeProps {
  task: Task;
  level: number;
}

function TaskTreeNode({ task, level }: TaskTreeNodeProps) {
  const [expanded, setExpanded] = useState(level < 1);
  const hasChildren = task.children && task.children.length > 0;
  const TypeIcon = typeIcons[task.type];
  const statusColor = STATUS_COLORS[task.status];

  return (
    <div>
      <div
        className={cn(
          'flex items-center gap-2 rounded-lg border p-3 mb-1 hover:bg-accent/50 transition-colors group',
          level > 0 && 'ml-6'
        )}
      >
        {/* Health stripe */}
        <div className={cn('w-1 self-stretch rounded-full shrink-0', healthColor(task.progress, task.status))} />

        {/* Expand toggle */}
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn('shrink-0 p-0.5 rounded hover:bg-muted', !hasChildren && 'invisible')}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        <TypeIcon className="h-4 w-4 text-muted-foreground shrink-0" />

        <Link
          to={`/tasks/${task.id}`}
          className="flex-1 text-sm font-medium hover:underline truncate"
        >
          {task.title}
        </Link>

        <Badge className={`${statusColor.text} ${statusColor.bg} border-0 text-[10px]`}>
          {STATUS_LABELS[task.status]}
        </Badge>

        <div className="w-24 shrink-0 hidden sm:block">
          <div className="flex items-center gap-2">
            <Progress value={task.progress} className="h-1.5 flex-1" />
            <span className="text-[11px] text-muted-foreground w-8 text-right">{task.progress}%</span>
          </div>
        </div>

        {task.department?.name && (
          <Badge variant="outline" className="text-[10px] hidden md:inline-flex">
            {task.department.name}
          </Badge>
        )}

        {task.due_date && (
          <span className="text-[11px] text-muted-foreground whitespace-nowrap hidden lg:inline">
            {formatDateShort(task.due_date)}
          </span>
        )}

        {hasChildren && (
          <span className="text-[11px] text-muted-foreground">
            {task.children!.length} дочерн.
          </span>
        )}
      </div>

      {expanded && hasChildren && (
        <div>
          {task.children!.map((child) => (
            <TaskTreeNode key={child.id} task={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

interface TaskTreeProps {
  tasks: Task[];
}

export function TaskTree({ tasks }: TaskTreeProps) {
  if (tasks.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Target className="mx-auto h-12 w-12 mb-4 opacity-50" />
        <p>Нет стратегических целей</p>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {tasks.map((task) => (
        <TaskTreeNode key={task.id} task={task} level={0} />
      ))}
    </div>
  );
}
