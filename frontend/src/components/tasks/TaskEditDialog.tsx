import { useState, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { updateTask } from '@/api/tasks';
import { getDepartments } from '@/api/departments';
import { getUsers } from '@/api/users';
import {
  ALL_STATUSES,
  ALL_PRIORITIES,
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
} from '@/lib/statusUtils';
import { toInputDate } from '@/lib/dateUtils';
import type { Task, TaskDetail, UpdateTaskPayload, Status, Priority } from '@/types';

interface TaskEditDialogProps {
  task: Task | TaskDetail;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Sentinel used so radix Select can represent "no selection" (null). */
const NONE = '_none';

export function TaskEditDialog({ task, open, onOpenChange }: TaskEditDialogProps) {
  const queryClient = useQueryClient();

  // ---- local form state, reset whenever `task` or `open` changes ----
  const [title, setTitle] = useState(task.title);
  const [description, setDescription] = useState(task.description ?? '');
  const [status, setStatus] = useState<Status>(task.status);
  const [priority, setPriority] = useState<Priority>(task.priority);
  const [assigneeId, setAssigneeId] = useState<string>(task.assignee_id ?? NONE);
  const [departmentId, setDepartmentId] = useState<string>(task.assigned_department_id ?? NONE);
  const [dueDate, setDueDate] = useState(toInputDate(task.due_date));
  const [progress, setProgress] = useState(task.progress);

  useEffect(() => {
    if (open) {
      setTitle(task.title);
      setDescription(task.description ?? '');
      setStatus(task.status);
      setPriority(task.priority);
      setAssigneeId(task.assignee_id ?? NONE);
      setDepartmentId(task.assigned_department_id ?? NONE);
      setDueDate(toInputDate(task.due_date));
      setProgress(task.progress);
    }
  }, [open, task]);

  // ---- data for selects ----
  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
    enabled: open,
  });

  const activeDeptId = departmentId === NONE ? undefined : departmentId;

  const { data: users } = useQuery({
    queryKey: ['users', activeDeptId],
    queryFn: () => getUsers(activeDeptId ? { department_id: activeDeptId } : undefined),
    enabled: open,
  });

  // ---- mutation ----
  const saveMutation = useMutation({
    mutationFn: (payload: UpdateTaskPayload) => updateTask(task.id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', task.id] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['analytics'] });
      onOpenChange(false);
    },
  });

  const handleSave = useCallback(() => {
    // Build a partial payload with only the fields that actually changed.
    const payload: UpdateTaskPayload = {};

    if (title !== task.title) payload.title = title;
    if (description !== (task.description ?? '')) payload.description = description;
    if (status !== task.status) payload.status = status;
    if (priority !== task.priority) payload.priority = priority;

    const newAssignee = assigneeId === NONE ? null : assigneeId;
    if (newAssignee !== (task.assignee_id ?? null)) payload.assignee_id = newAssignee;

    const newDept = departmentId === NONE ? null : departmentId;
    if (newDept !== (task.assigned_department_id ?? null)) payload.assigned_department_id = newDept;

    const newDue = dueDate || null;
    const oldDue = toInputDate(task.due_date) || null;
    if (newDue !== oldDue) payload.due_date = newDue;

    if (progress !== task.progress) payload.progress = progress;

    // Nothing changed -- just close.
    if (Object.keys(payload).length === 0) {
      onOpenChange(false);
      return;
    }

    saveMutation.mutate(payload);
  }, [
    title, description, status, priority, assigneeId, departmentId,
    dueDate, progress, task, saveMutation, onOpenChange,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Редактировать задачу</DialogTitle>
          <DialogDescription>Измените нужные поля и сохраните</DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Title */}
          <div>
            <Label>Название</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1.5"
              placeholder="Название задачи"
            />
          </div>

          {/* Description */}
          <div>
            <Label>Описание</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1.5"
              rows={3}
              placeholder="Описание задачи..."
            />
          </div>

          {/* Status + Priority */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Статус</Label>
              <Select value={status} onValueChange={(v) => setStatus(v as Status)}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      <div className="flex items-center gap-2">
                        <div className={`h-2 w-2 rounded-full ${STATUS_COLORS[s].dot}`} />
                        {STATUS_LABELS[s]}
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Приоритет</Label>
              <Select value={priority} onValueChange={(v) => setPriority(v as Priority)}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALL_PRIORITIES.map((p) => (
                    <SelectItem key={p} value={p}>
                      {PRIORITY_LABELS[p]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Department + Assignee */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Отдел</Label>
              <Select
                value={departmentId}
                onValueChange={(v) => {
                  setDepartmentId(v);
                  // Reset assignee when department changes so we don't
                  // keep a user from the wrong department selected.
                  setAssigneeId(NONE);
                }}
              >
                <SelectTrigger className="mt-1.5">
                  <SelectValue placeholder="Выберите отдел" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>&mdash; Без отдела &mdash;</SelectItem>
                  {departments?.map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Исполнитель</Label>
              <Select value={assigneeId} onValueChange={(v) => setAssigneeId(v)}>
                <SelectTrigger className="mt-1.5">
                  <SelectValue placeholder="Выберите исполнителя" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>&mdash; Не назначен &mdash;</SelectItem>
                  {users?.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Due date */}
          <div>
            <Label>Срок выполнения</Label>
            <Input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="mt-1.5"
            />
          </div>

          {/* Progress */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <Label>Прогресс</Label>
              <span className="text-sm text-muted-foreground">{progress}%</span>
            </div>
            <Slider
              value={[progress]}
              max={100}
              step={5}
              onValueChange={(v) => setProgress(v[0])}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={saveMutation.isPending || !title.trim()}>
            {saveMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
