import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ChevronDown,
  ChevronRight,
  Target,
  Mountain,
  ListTodo,
  CheckSquare,
  ArrowRight,
  Inbox,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { cn } from '@/lib/utils';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
} from '@/lib/statusUtils';
import { formatDateShort } from '@/lib/dateUtils';
import type { Task, TaskType } from '@/types';

const TYPE_ICONS: Record<TaskType, React.ElementType> = {
  GOAL: Target,
  EPIC: Mountain,
  TASK: ListTodo,
  SUBTASK: CheckSquare,
};

const TYPE_LABELS: Record<TaskType, string> = {
  GOAL: 'Цель',
  EPIC: 'Эпик',
  TASK: 'Задача',
  SUBTASK: 'Подзадача',
};

const TYPE_TINT: Record<TaskType, string> = {
  GOAL: 'text-violet-500',
  EPIC: 'text-blue-500',
  TASK: 'text-cyan-500',
  SUBTASK: 'text-muted-foreground',
};

interface TaskNode extends Omit<Task, 'children'> {
  children: TaskNode[];
}

function buildForest(tasks: Task[]): TaskNode[] {
  const byId = new Map<string, TaskNode>();
  tasks.forEach((t) => byId.set(t.id, { ...t, children: [] }));
  const roots: TaskNode[] = [];
  byId.forEach((node) => {
    if (node.parent_id && byId.has(node.parent_id)) {
      byId.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  // Sort: GOALs first, then by type, then by due_date
  const typeOrder: TaskType[] = ['GOAL', 'EPIC', 'TASK', 'SUBTASK'];
  const sortFn = (a: TaskNode, b: TaskNode) => {
    const oa = typeOrder.indexOf(a.type);
    const ob = typeOrder.indexOf(b.type);
    if (oa !== ob) return oa - ob;
    return (a.due_date ?? '') < (b.due_date ?? '') ? -1 : 1;
  };
  const sortRec = (node: TaskNode) => {
    node.children.sort(sortFn);
    node.children.forEach(sortRec);
  };
  roots.sort(sortFn);
  roots.forEach(sortRec);
  return roots;
}

function initials(name?: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '');
}

/** A single tree node row — shows delegation (assignee + dept) prominently. */
function TreeNode({
  node,
  level,
  parentDeptId,
}: {
  node: TaskNode;
  level: number;
  parentDeptId?: string | null;
}) {
  const [expanded, setExpanded] = useState(level < 1);
  const hasChildren = node.children.length > 0;
  const TypeIcon = TYPE_ICONS[node.type];
  const statusColor = STATUS_COLORS[node.status];
  const priorityColor = PRIORITY_COLORS[node.priority];

  // Delegation marker: child's dept differs from parent's
  const deptChanged =
    !!parentDeptId &&
    !!node.assigned_department_id &&
    parentDeptId !== node.assigned_department_id;

  return (
    <div>
      <div
        className={cn(
          'group flex items-center gap-2 rounded-md py-2 px-2 hover:bg-muted/40 transition-colors',
          'border-l-2',
          deptChanged ? 'border-l-amber-500/60' : 'border-l-transparent'
        )}
        style={{ marginLeft: `${level * 20}px` }}
      >
        <button
          onClick={() => setExpanded(!expanded)}
          className={cn(
            'shrink-0 p-0.5 rounded hover:bg-muted',
            !hasChildren && 'invisible'
          )}
          aria-label="Свернуть/развернуть"
        >
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </button>

        <TypeIcon className={cn('h-4 w-4 shrink-0', TYPE_TINT[node.type])} />

        <Link
          to={`/tasks/${node.id}`}
          className="flex-1 min-w-0 text-sm font-medium hover:underline truncate"
          title={node.title}
        >
          {node.title}
        </Link>

        {/* Status */}
        <Badge
          className={`${statusColor.text} ${statusColor.bg} border-0 text-[10px] shrink-0`}
        >
          {STATUS_LABELS[node.status]}
        </Badge>

        {/* Priority dot */}
        <span
          className={cn('text-[10px] hidden md:inline shrink-0', priorityColor.text)}
          title={`Приоритет: ${PRIORITY_LABELS[node.priority]}`}
        >
          ●
        </span>

        {/* Progress (compact) */}
        <div className="w-20 shrink-0 hidden sm:block">
          <div className="flex items-center gap-1.5">
            <Progress value={node.progress} className="h-1 flex-1" />
            <span className="text-[10px] text-muted-foreground w-7 text-right">
              {node.progress}%
            </span>
          </div>
        </div>

        {/* Assignee */}
        {node.assignee_name ? (
          <div className="flex items-center gap-1.5 shrink-0 min-w-0 max-w-[160px]">
            <Avatar className="h-5 w-5">
              <AvatarFallback className="text-[9px] bg-primary/15 text-primary">
                {initials(node.assignee_name)}
              </AvatarFallback>
            </Avatar>
            <span className="text-[11px] text-muted-foreground truncate hidden lg:inline">
              {node.assignee_name}
            </span>
          </div>
        ) : (
          <span className="text-[11px] text-muted-foreground italic hidden lg:inline shrink-0">
            не назначен
          </span>
        )}

        {/* Department (with delegation arrow if changed) */}
        {node.assigned_department_name && (
          <div className="flex items-center gap-1 shrink-0 hidden xl:flex">
            {deptChanged && (
              <ArrowRight
                className="h-3 w-3 text-amber-500"
                aria-label="Передано в другой отдел"
              />
            )}
            <Badge variant="outline" className="text-[10px]">
              {node.assigned_department_name}
            </Badge>
          </div>
        )}

        {/* Due date */}
        {node.due_date && (
          <span className="text-[10px] text-muted-foreground whitespace-nowrap hidden lg:inline shrink-0">
            {formatDateShort(node.due_date)}
          </span>
        )}
      </div>

      {expanded && hasChildren && (
        <div className="border-l border-dashed border-border/40 ml-[18px]">
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              level={level + 1}
              parentDeptId={node.assigned_department_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** A big GOAL card with header summary and nested tree underneath. */
function GoalGroupCard({ goal }: { goal: TaskNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const statusColor = STATUS_COLORS[goal.status];
  const priorityColor = PRIORITY_COLORS[goal.priority];

  // Count descendants
  const descendantCount = (function count(n: TaskNode): number {
    return n.children.reduce((sum, c) => sum + 1 + count(c), 0);
  })(goal);

  // Collect involved departments
  const depts = new Set<string>();
  (function walk(n: TaskNode) {
    if (n.assigned_department_name) depts.add(n.assigned_department_name);
    n.children.forEach(walk);
  })(goal);

  return (
    <Card className="border-l-4 border-l-violet-500">
      <CardContent className="p-4">
        {/* Header row */}
        <div className="flex items-start gap-3 mb-3">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="shrink-0 mt-0.5 p-1 rounded hover:bg-muted"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </button>
          <Target className="h-5 w-5 text-violet-500 shrink-0 mt-1" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge
                variant="outline"
                className="text-[10px] text-violet-600 border-violet-500/40"
              >
                Стратегическая цель
              </Badge>
              <Badge
                className={`${statusColor.text} ${statusColor.bg} border-0 text-[10px]`}
              >
                {STATUS_LABELS[goal.status]}
              </Badge>
              <span className={cn('text-[10px]', priorityColor.text)}>
                ● {PRIORITY_LABELS[goal.priority]} приоритет
              </span>
            </div>
            <Link
              to={`/tasks/${goal.id}`}
              className="block mt-1 text-lg font-semibold hover:underline"
            >
              {goal.title}
            </Link>
            {goal.description && (
              <p className="text-sm text-muted-foreground mt-1 line-clamp-2">
                {goal.description}
              </p>
            )}
            <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground flex-wrap">
              {goal.assignee_name && (
                <span className="flex items-center gap-1.5">
                  <Avatar className="h-5 w-5">
                    <AvatarFallback className="text-[9px] bg-primary/15 text-primary">
                      {initials(goal.assignee_name)}
                    </AvatarFallback>
                  </Avatar>
                  <span>{goal.assignee_name}</span>
                </span>
              )}
              {goal.assigned_department_name && (
                <span className="flex items-center gap-1">
                  📁 {goal.assigned_department_name}
                </span>
              )}
              {goal.due_date && <span>📅 до {formatDateShort(goal.due_date)}</span>}
              <span>
                {descendantCount} дочерних задач • {depts.size} отдел(ов) вовлечено
              </span>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <Progress value={goal.progress} className="h-2 flex-1 max-w-md" />
              <span className="text-sm font-medium w-10 text-right">
                {goal.progress}%
              </span>
            </div>
          </div>
        </div>

        {/* Nested tree */}
        {!collapsed && goal.children.length > 0 && (
          <div className="mt-3 pt-3 border-t border-border/40">
            {goal.children.map((child) => (
              <TreeNode
                key={child.id}
                node={child}
                level={0}
                parentDeptId={goal.assigned_department_id}
              />
            ))}
          </div>
        )}
        {!collapsed && goal.children.length === 0 && (
          <p className="text-sm text-muted-foreground italic mt-2">
            Пока нет декомпозиции на эпики/задачи
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export function TaskStrategyView({ tasks }: { tasks: Task[] }) {
  const { goals, orphans } = useMemo(() => {
    const forest = buildForest(tasks);
    const g: TaskNode[] = [];
    const o: TaskNode[] = [];
    forest.forEach((root) => (root.type === 'GOAL' ? g : o).push(root));
    return { goals: g, orphans: o };
  }, [tasks]);

  if (goals.length === 0 && orphans.length === 0) {
    return (
      <div className="text-center py-16">
        <Target className="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
        <h3 className="text-lg font-medium mb-1">Нет задач</h3>
        <p className="text-sm text-muted-foreground">
          Создайте первую стратегическую цель и декомпозируйте её на задачи
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-3 w-1 bg-violet-500 rounded" />
          Цель
        </span>
        <span className="flex items-center gap-1.5">
          <Mountain className="h-3 w-3 text-blue-500" />
          Эпик
        </span>
        <span className="flex items-center gap-1.5">
          <ListTodo className="h-3 w-3 text-cyan-500" />
          Задача
        </span>
        <span className="flex items-center gap-1.5">
          <CheckSquare className="h-3 w-3" />
          Подзадача
        </span>
        <span className="text-border">|</span>
        <span className="flex items-center gap-1.5">
          <ArrowRight className="h-3 w-3 text-amber-500" />
          Передача в другой отдел
        </span>
      </div>

      {/* Strategic goal cards */}
      {goals.map((goal) => (
        <GoalGroupCard key={goal.id} goal={goal} />
      ))}

      {/* Orphan tasks (no parent goal) */}
      {orphans.length > 0 && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Inbox className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold">
                Без стратегической цели ({orphans.length})
              </h3>
            </div>
            <p className="text-xs text-muted-foreground mb-3">
              Эти задачи не привязаны ни к одной из стратегических целей —
              операционная работа, поддержка, разовые активности.
            </p>
            <div>
              {orphans.map((task) => (
                <TreeNode key={task.id} node={task} level={0} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
