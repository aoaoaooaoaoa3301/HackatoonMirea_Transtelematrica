import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { KanbanBoard } from '@/components/tasks/KanbanBoard';
import { TaskFormDialog } from '@/components/tasks/TaskFormDialog';
import { getTasks, updateTask } from '@/api/tasks';
import { getDepartments } from '@/api/departments';
import { getUsers } from '@/api/users';
import {
  ALL_TASK_TYPES,
  TASK_TYPE_LABELS,
} from '@/lib/statusUtils';
import type { Status, TaskType } from '@/types';

export default function KanbanPage() {
  const queryClient = useQueryClient();
  const [departmentId, setDepartmentId] = useState<string>('');
  const [assigneeId, setAssigneeId] = useState<string>('');
  const [taskType, setTaskType] = useState<string>('');
  const [dialogOpen, setDialogOpen] = useState(false);

  const filters: Record<string, string | undefined> = {};
  if (departmentId) filters.department_id = departmentId;
  if (assigneeId) filters.assignee_id = assigneeId;

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks', 'kanban', departmentId, assigneeId, taskType],
    queryFn: () =>
      getTasks({
        department_id: departmentId || undefined,
        assignee_id: assigneeId || undefined,
        type: taskType ? [taskType as TaskType] : undefined,
      }),
  });

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
  });

  const { data: users } = useQuery({
    queryKey: ['users', departmentId],
    queryFn: () => getUsers(departmentId ? { department_id: departmentId } : undefined),
  });

  const statusMutation = useMutation({
    mutationFn: ({ taskId, status }: { taskId: string; status: Status }) =>
      updateTask(taskId, { status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const handleStatusChange = (taskId: string, newStatus: Status) => {
    statusMutation.mutate({ taskId, status: newStatus });
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={departmentId || '_all'} onValueChange={(v) => { setDepartmentId(v === '_all' ? '' : v); setAssigneeId(''); }}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="Все отделы" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Все отделы</SelectItem>
            {departments?.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={assigneeId || '_all'} onValueChange={(v) => setAssigneeId(v === '_all' ? '' : v)}>
          <SelectTrigger className="w-full sm:w-48">
            <SelectValue placeholder="Все исполнители" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Все исполнители</SelectItem>
            {users?.map((u) => (
              <SelectItem key={u.id} value={u.id}>{u.full_name}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={taskType || '_all'} onValueChange={(v) => setTaskType(v === '_all' ? '' : v)}>
          <SelectTrigger className="w-full sm:w-40">
            <SelectValue placeholder="Все типы" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="_all">Все типы</SelectItem>
            {ALL_TASK_TYPES.map((t) => (
              <SelectItem key={t} value={t}>{TASK_TYPE_LABELS[t]}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex-1" />
        {/* Topbar already provides a global create on mobile — avoid a duplicate "+" */}
        <Button className="hidden sm:inline-flex" onClick={() => setDialogOpen(true)}>
          <Plus className="h-4 w-4 sm:mr-1" />
          <span className="hidden sm:inline">Создать</span>
        </Button>
      </div>

      {/* Board */}
      {isLoading ? (
        <div className="flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="w-72 h-96 shrink-0" />
          ))}
        </div>
      ) : (
        <KanbanBoard tasks={tasks ?? []} onStatusChange={handleStatusChange} />
      )}

      <TaskFormDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
