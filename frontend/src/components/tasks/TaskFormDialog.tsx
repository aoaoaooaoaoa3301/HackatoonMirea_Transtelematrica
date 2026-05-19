import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Sparkles, Loader2, User as UserIcon } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { createTask } from '@/api/tasks';
import { getDepartments } from '@/api/departments';
import { getUsers } from '@/api/users';
import { parseTask, suggestAssignee } from '@/api/ai';
import {
  ALL_TASK_TYPES,
  ALL_PRIORITIES,
  TASK_TYPE_LABELS,
  PRIORITY_LABELS,
  PERIOD_LABELS,
  ALL_PERIOD_BUCKETS,
} from '@/lib/statusUtils';
import type { CreateTaskPayload, AIAssigneeCandidate } from '@/types';

const taskSchema = z.object({
  type: z.enum(['GOAL', 'EPIC', 'TASK', 'SUBTASK']),
  title: z.string().min(1, 'Название обязательно'),
  description: z.string().optional(),
  priority: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
  period_bucket: z.enum(['year', 'quarter', 'month', 'week']).optional(),
  due_date: z.string().optional(),
  start_date: z.string().optional(),
  assigned_department_id: z.string().optional(),
  assignee_id: z.string().optional(),
  parent_id: z.string().optional(),
});

type TaskFormData = z.infer<typeof taskSchema>;

interface TaskFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  parentId?: string;
  defaultType?: 'GOAL' | 'EPIC' | 'TASK' | 'SUBTASK';
}

export function TaskFormDialog({
  open,
  onOpenChange,
  parentId,
  defaultType,
}: TaskFormDialogProps) {
  const queryClient = useQueryClient();
  const [aiText, setAiText] = useState('');
  const [aiParsing, setAiParsing] = useState(false);
  const [candidates, setCandidates] = useState<AIAssigneeCandidate[]>([]);
  const [suggestLoading, setSuggestLoading] = useState(false);

  const form = useForm<TaskFormData>({
    resolver: zodResolver(taskSchema),
    defaultValues: {
      type: defaultType ?? 'TASK',
      title: '',
      description: '',
      priority: 'MEDIUM',
      period_bucket: 'month',
      assigned_department_id: '',
      assignee_id: '',
      parent_id: parentId ?? '',
    },
  });

  const deptId = form.watch('assigned_department_id');

  const { data: departments } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
    enabled: open,
  });

  const { data: users } = useQuery({
    queryKey: ['users', deptId],
    queryFn: () => getUsers(deptId ? { department_id: deptId } : undefined),
    enabled: open,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateTaskPayload) => createTask(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      form.reset();
      setCandidates([]);
      onOpenChange(false);
    },
  });

  const onSubmit = (data: TaskFormData) => {
    const payload: CreateTaskPayload = {
      ...data,
      assigned_department_id: data.assigned_department_id || null,
      assignee_id: data.assignee_id || null,
      parent_id: data.parent_id || null,
      due_date: data.due_date || null,
      start_date: data.start_date || null,
    };
    createMutation.mutate(payload);
  };

  const handleAIParse = async () => {
    if (!aiText.trim()) return;
    setAiParsing(true);
    try {
      const result = await parseTask(aiText);
      form.setValue('title', result.title);
      if (result.description) form.setValue('description', result.description);
      if (result.due_date) form.setValue('due_date', result.due_date);
      form.setValue('priority', result.priority);
      form.setValue('type', result.type);
    } catch {
      // AI unavailable, ignore
    } finally {
      setAiParsing(false);
    }
  };

  const handleSuggestAssignee = async () => {
    const title = form.getValues('title');
    if (!title) return;
    setSuggestLoading(true);
    try {
      const result = await suggestAssignee({
        title,
        description: form.getValues('description'),
        department_id: form.getValues('assigned_department_id') || undefined,
        priority: form.getValues('priority'),
        due_date: form.getValues('due_date') || undefined,
      });
      setCandidates(result.candidates ?? []);
    } catch {
      // AI unavailable
    } finally {
      setSuggestLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Создать задачу</DialogTitle>
          <DialogDescription>
            Заполните форму вручную или используйте AI для распознавания
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="manual" className="w-full">
          <TabsList className="w-full">
            <TabsTrigger value="manual" className="flex-1">Вручную</TabsTrigger>
            <TabsTrigger value="ai" className="flex-1">
              <Sparkles className="mr-1.5 h-3.5 w-3.5" />
              Через AI
            </TabsTrigger>
          </TabsList>

          <TabsContent value="ai" className="space-y-4 mt-4">
            <div>
              <Label>Опишите задачу</Label>
              <Textarea
                value={aiText}
                onChange={(e) => setAiText(e.target.value)}
                placeholder="Например: Нужно до конца месяца подготовить отчёт по продажам для отдела маркетинга, критический приоритет"
                rows={4}
                className="mt-1.5"
              />
            </div>
            <Button onClick={handleAIParse} disabled={aiParsing || !aiText.trim()}>
              {aiParsing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="mr-2 h-4 w-4" />
              )}
              Распознать
            </Button>
            {form.getValues('title') && (
              <p className="text-sm text-muted-foreground">
                Данные заполнены. Переключитесь на вкладку «Вручную» для проверки и отправки.
              </p>
            )}
          </TabsContent>

          <TabsContent value="manual" className="mt-4">
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Тип</Label>
                  <Select
                    value={form.watch('type')}
                    onValueChange={(v) => form.setValue('type', v as TaskFormData['type'])}
                  >
                    <SelectTrigger className="mt-1.5">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {ALL_TASK_TYPES.map((t) => (
                        <SelectItem key={t} value={t}>
                          {TASK_TYPE_LABELS[t]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Приоритет</Label>
                  <Select
                    value={form.watch('priority')}
                    onValueChange={(v) => form.setValue('priority', v as TaskFormData['priority'])}
                  >
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

              <div>
                <Label>Название</Label>
                <Input {...form.register('title')} className="mt-1.5" placeholder="Название задачи" />
                {form.formState.errors.title && (
                  <p className="text-xs text-destructive mt-1">{form.formState.errors.title.message}</p>
                )}
              </div>

              <div>
                <Label>Описание</Label>
                <Textarea {...form.register('description')} className="mt-1.5" rows={3} placeholder="Описание задачи..." />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Дата начала</Label>
                  <Input type="date" {...form.register('start_date')} className="mt-1.5" />
                </div>
                <div>
                  <Label>Срок выполнения</Label>
                  <Input type="date" {...form.register('due_date')} className="mt-1.5" />
                </div>
              </div>

              <div>
                <Label>Период</Label>
                <Select
                  value={form.watch('period_bucket') ?? 'month'}
                  onValueChange={(v) => form.setValue('period_bucket', v as TaskFormData['period_bucket'])}
                >
                  <SelectTrigger className="mt-1.5">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ALL_PERIOD_BUCKETS.map((p) => (
                      <SelectItem key={p} value={p}>
                        {PERIOD_LABELS[p]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Отдел</Label>
                  <Select
                    value={form.watch('assigned_department_id') || '_none'}
                    onValueChange={(v) => {
                      form.setValue('assigned_department_id', v === '_none' ? '' : v);
                      form.setValue('assignee_id', '');
                      setCandidates([]);
                    }}
                  >
                    <SelectTrigger className="mt-1.5">
                      <SelectValue placeholder="Выберите отдел" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_none">Не выбран</SelectItem>
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
                  <Select
                    value={form.watch('assignee_id') || '_none'}
                    onValueChange={(v) => form.setValue('assignee_id', v === '_none' ? '' : v)}
                  >
                    <SelectTrigger className="mt-1.5">
                      <SelectValue placeholder="Выберите исполнителя" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="_none">Не назначен</SelectItem>
                      {users?.map((u) => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* AI suggestions */}
              <div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleSuggestAssignee}
                  disabled={suggestLoading || !form.watch('title')}
                >
                  {suggestLoading ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  AI рекомендует
                </Button>
                {candidates.length > 0 && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    <TooltipProvider>
                      {candidates.slice(0, 3).map((c) => (
                        <Tooltip key={c.user_id}>
                          <TooltipTrigger asChild>
                            <Badge
                              variant="secondary"
                              className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors"
                              onClick={() => form.setValue('assignee_id', c.user_id)}
                            >
                              <UserIcon className="mr-1 h-3 w-3" />
                              {c.full_name} ({Math.round(c.score * 100)}%)
                            </Badge>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="max-w-xs text-xs">{c.reason}</p>
                          </TooltipContent>
                        </Tooltip>
                      ))}
                    </TooltipProvider>
                  </div>
                )}
              </div>

              {parentId && <input type="hidden" {...form.register('parent_id')} />}

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Отмена
                </Button>
                <Button type="submit" disabled={createMutation.isPending}>
                  {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Создать
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
