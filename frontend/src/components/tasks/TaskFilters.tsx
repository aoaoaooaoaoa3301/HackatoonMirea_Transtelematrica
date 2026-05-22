import { useQuery } from '@tanstack/react-query';
import { Search, X } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ALL_STATUSES,
  ALL_PRIORITIES,
  ALL_TASK_TYPES,
  STATUS_LABELS,
  PRIORITY_LABELS,
  TASK_TYPE_LABELS,
  STATUS_COLORS,
  PRIORITY_COLORS,
} from '@/lib/statusUtils';
import { getDepartments } from '@/api/departments';
import { getUsers } from '@/api/users';
import type { TaskFilters as TFilters, Status, Priority, TaskType } from '@/types';

interface TaskFiltersProps {
  filters: TFilters;
  onChange: (filters: TFilters) => void;
}

export function TaskFilters({ filters, onChange }: TaskFiltersProps) {
  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
  });

  const { data: users } = useQuery({
    queryKey: ['users', filters.department_id],
    queryFn: () => getUsers(filters.department_id ? { department_id: filters.department_id } : undefined),
  });

  const toggleArrayFilter = <T extends string>(
    key: 'type' | 'status' | 'priority',
    value: T
  ) => {
    const current = (filters[key] as T[] | undefined) ?? [];
    const next = current.includes(value)
      ? current.filter((v) => v !== value)
      : [...current, value];
    onChange({ ...filters, [key]: next.length > 0 ? next : undefined });
  };

  const hasFilters =
    (filters.type?.length ?? 0) > 0 ||
    (filters.status?.length ?? 0) > 0 ||
    (filters.priority?.length ?? 0) > 0 ||
    !!filters.department_id ||
    !!filters.assignee_id ||
    !!filters.q;

  return (
    <div className="space-y-3">
      {/* Search row */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="relative w-full sm:flex-1 sm:max-w-sm">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Поиск задач..."
            value={filters.q ?? ''}
            onChange={(e) => onChange({ ...filters, q: e.target.value || undefined })}
            className="pl-8"
          />
        </div>

        <Select
          value={filters.department_id ?? '_all'}
          onValueChange={(v) =>
            onChange({ ...filters, department_id: v === '_all' ? undefined : v, assignee_id: undefined })
          }
        >
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="Все отделы" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Все отделы</SelectItem>
            {departments?.map((d) => (
              <SelectItem key={d.id} value={d.id}>
                {d.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={filters.assignee_id ?? '_all'}
          onValueChange={(v) => onChange({ ...filters, assignee_id: v === '_all' ? undefined : v })}
        >
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="Все исполнители" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Все исполнители</SelectItem>
            {users?.map((u) => (
              <SelectItem key={u.id} value={u.id}>
                {u.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange({})}
            className="text-muted-foreground"
          >
            <X className="mr-1 h-3 w-3" />
            Сбросить
          </Button>
        )}
      </div>

      {/* Filter chips */}
      <div className="flex flex-wrap gap-2">
        {/* Type chips */}
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1">Тип:</span>
          {ALL_TASK_TYPES.map((t) => (
            <Badge
              key={t}
              variant={filters.type?.includes(t) ? 'default' : 'outline'}
              className="cursor-pointer text-[11px]"
              onClick={() => toggleArrayFilter<TaskType>('type', t)}
            >
              {TASK_TYPE_LABELS[t]}
            </Badge>
          ))}
        </div>

        <div className="h-6 w-px bg-border hidden sm:block" />

        {/* Status chips */}
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1">Статус:</span>
          {ALL_STATUSES.map((s) => {
            const active = filters.status?.includes(s);
            const colors = STATUS_COLORS[s];
            return (
              <Badge
                key={s}
                className={`cursor-pointer text-[11px] border-0 ${
                  active ? `${colors.text} ${colors.bg}` : 'bg-muted text-muted-foreground'
                }`}
                onClick={() => toggleArrayFilter<Status>('status', s)}
              >
                {STATUS_LABELS[s]}
              </Badge>
            );
          })}
        </div>

        <div className="h-6 w-px bg-border hidden sm:block" />

        {/* Priority chips */}
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1">Приоритет:</span>
          {ALL_PRIORITIES.map((p) => {
            const active = filters.priority?.includes(p);
            const colors = PRIORITY_COLORS[p];
            return (
              <Badge
                key={p}
                className={`cursor-pointer text-[11px] border-0 ${
                  active ? `${colors.text} ${colors.bg}` : 'bg-muted text-muted-foreground'
                }`}
                onClick={() => toggleArrayFilter<Priority>('priority', p)}
              >
                {PRIORITY_LABELS[p]}
              </Badge>
            );
          })}
        </div>
      </div>
    </div>
  );
}
