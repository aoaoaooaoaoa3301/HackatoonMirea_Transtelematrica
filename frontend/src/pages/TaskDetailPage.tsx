import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  ChevronRight,
  Target,
  Mountain,
  ListTodo,
  CheckSquare,
  MessageSquare,
  History,
  Plus,
  Send,
  Loader2,
  Edit3,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Slider } from '@/components/ui/slider';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { TaskCard } from '@/components/tasks/TaskCard';
import { TaskFormDialog } from '@/components/tasks/TaskFormDialog';
import { getTask, updateTask, addComment } from '@/api/tasks';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
  TASK_TYPE_LABELS,
  ALL_STATUSES,
  ALL_PRIORITIES,
  TASK_EVENT_LABELS,
} from '@/lib/statusUtils';
import { formatDate, formatDateTime, formatRelative } from '@/lib/dateUtils';
import type { TaskType, Status, Priority } from '@/types';

const typeIcons: Record<TaskType, React.ElementType> = {
  GOAL: Target,
  EPIC: Mountain,
  TASK: ListTodo,
  SUBTASK: CheckSquare,
};

export default function TaskDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [commentText, setCommentText] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [editingDesc, setEditingDesc] = useState(false);
  const [descDraft, setDescDraft] = useState('');
  const [subDialogOpen, setSubDialogOpen] = useState(false);

  const { data: task, isLoading } = useQuery({
    queryKey: ['task', id],
    queryFn: () => getTask(id!),
    enabled: !!id,
  });

  const updateMutation = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateTask(id!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', id] });
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const commentMutation = useMutation({
    mutationFn: (body: string) => addComment(id!, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['task', id] });
      setCommentText('');
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-96" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <Skeleton className="h-48" />
            <Skeleton className="h-32" />
          </div>
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="text-center py-16">
        <p className="text-muted-foreground">Задача не найдена</p>
      </div>
    );
  }

  const TypeIcon = typeIcons[task.type];
  const statusColor = STATUS_COLORS[task.status];
  const assigneeName = task.assignee_name ?? task.assignee?.full_name ?? null;
  const departmentName = task.assigned_department_name ?? task.department?.name ?? null;
  const assigneeInitials = assigneeName
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2);

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      {task.parent_chain && task.parent_chain.length > 0 && (
        <nav className="flex items-center gap-1 text-sm text-muted-foreground flex-wrap">
          {task.parent_chain.map((parent, i) => (
            <span key={parent.id} className="flex items-center gap-1">
              <Link to={`/tasks/${parent.id}`} className="hover:text-foreground transition-colors">
                {parent.title}
              </Link>
              <ChevronRight className="h-3 w-3" />
            </span>
          ))}
          <span className="text-foreground font-medium">{task.title}</span>
        </nav>
      )}

      {/* Header */}
      <div className="flex items-start gap-4">
        <div className="rounded-lg bg-muted p-3">
          <TypeIcon className="h-6 w-6 text-muted-foreground" />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className="text-xs">{TASK_TYPE_LABELS[task.type]}</Badge>
            <Badge className={`${statusColor.text} ${statusColor.bg} border-0`}>
              {STATUS_LABELS[task.status]}
            </Badge>
          </div>
          {editingTitle ? (
            <div className="flex items-center gap-2 mt-1">
              <Input
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                className="text-xl font-bold"
                autoFocus
              />
              <Button
                size="sm"
                onClick={() => {
                  updateMutation.mutate({ title: titleDraft });
                  setEditingTitle(false);
                }}
              >
                Сохранить
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setEditingTitle(false)}>
                Отмена
              </Button>
            </div>
          ) : (
            <h1
              className="text-xl font-bold cursor-pointer hover:text-primary/80 transition-colors group flex items-center gap-2"
              onClick={() => {
                setTitleDraft(task.title);
                setEditingTitle(true);
              }}
            >
              {task.title}
              <Edit3 className="h-4 w-4 opacity-0 group-hover:opacity-50 transition-opacity" />
            </h1>
          )}
        </div>
      </div>

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Описание</CardTitle>
            </CardHeader>
            <CardContent>
              {editingDesc ? (
                <div className="space-y-2">
                  <Textarea
                    value={descDraft}
                    onChange={(e) => setDescDraft(e.target.value)}
                    rows={4}
                  />
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => {
                        updateMutation.mutate({ description: descDraft });
                        setEditingDesc(false);
                      }}
                    >
                      Сохранить
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setEditingDesc(false)}>
                      Отмена
                    </Button>
                  </div>
                </div>
              ) : (
                <p
                  className="text-sm text-muted-foreground whitespace-pre-wrap cursor-pointer hover:bg-accent/30 rounded p-2 -m-2 transition-colors"
                  onClick={() => {
                    setDescDraft(task.description || '');
                    setEditingDesc(true);
                  }}
                >
                  {task.description || 'Нажмите, чтобы добавить описание...'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Children */}
          {task.children && task.children.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">
                    Подзадачи ({task.children.length})
                  </CardTitle>
                  <Button size="sm" variant="outline" onClick={() => setSubDialogOpen(true)}>
                    <Plus className="mr-1 h-3 w-3" />
                    Добавить
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-1">
                  {task.children.map((child) => (
                    <TaskCard key={child.id} task={child} compact />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {task.children?.length === 0 && task.type !== 'SUBTASK' && (
            <Card>
              <CardContent className="p-6 text-center">
                <p className="text-sm text-muted-foreground mb-3">Нет подзадач</p>
                <Button size="sm" variant="outline" onClick={() => setSubDialogOpen(true)}>
                  <Plus className="mr-1 h-3 w-3" />
                  Создать подзадачу
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Comments */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Комментарии ({task.comments?.length ?? 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {task.comments?.map((comment) => {
                  const initials = comment.author?.full_name
                    ?.split(' ')
                    .map((n) => n[0])
                    .join('')
                    .slice(0, 2);
                  return (
                    <div key={comment.id} className="flex gap-3">
                      <Avatar className="h-8 w-8 shrink-0">
                        <AvatarFallback className="text-xs bg-primary/10">{initials}</AvatarFallback>
                      </Avatar>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-sm font-medium">{comment.author?.full_name}</span>
                          <span className="text-xs text-muted-foreground">
                            {formatRelative(comment.created_at)}
                          </span>
                        </div>
                        <p className="text-sm text-muted-foreground">{comment.body}</p>
                      </div>
                    </div>
                  );
                })}
                {(task.comments?.length ?? 0) === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    Нет комментариев
                  </p>
                )}
              </div>

              <Separator className="my-4" />

              <div className="flex gap-2">
                <Textarea
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="Написать комментарий..."
                  rows={2}
                  className="flex-1"
                />
                <Button
                  size="icon"
                  onClick={() => commentText.trim() && commentMutation.mutate(commentText.trim())}
                  disabled={!commentText.trim() || commentMutation.isPending}
                >
                  {commentMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Right column - meta */}
        <div className="space-y-4">
          <Card>
            <CardContent className="p-4 space-y-4">
              {/* Status */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Статус</p>
                <Select
                  value={task.status}
                  onValueChange={(v) => updateMutation.mutate({ status: v as Status })}
                >
                  <SelectTrigger>
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

              {/* Priority */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Приоритет</p>
                <Select
                  value={task.priority}
                  onValueChange={(v) => updateMutation.mutate({ priority: v as Priority })}
                >
                  <SelectTrigger>
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

              <Separator />

              {/* Assignee */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Исполнитель</p>
                {assigneeName ? (
                  <div className="flex items-center gap-2">
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="text-[10px] bg-primary/10">
                        {assigneeInitials}
                      </AvatarFallback>
                    </Avatar>
                    <span className="text-sm">{assigneeName}</span>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Не назначен</p>
                )}
              </div>

              {/* Department */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Отдел</p>
                <p className="text-sm">{departmentName ?? 'Не указан'}</p>
              </div>

              <Separator />

              {/* Dates */}
              <div>
                <p className="text-xs text-muted-foreground mb-1">Начало</p>
                <p className="text-sm">{formatDate(task.start_date)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Срок</p>
                <p className="text-sm">{formatDate(task.due_date)}</p>
              </div>

              <Separator />

              {/* Progress */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs text-muted-foreground">Прогресс</p>
                  <span className="text-sm font-medium">{task.progress}%</span>
                </div>
                <Slider
                  value={[task.progress]}
                  max={100}
                  step={5}
                  onValueCommit={(v) => updateMutation.mutate({ progress: v[0] })}
                />
              </div>

              <Separator />

              {/* Create subtask */}
              {task.type !== 'SUBTASK' && (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => setSubDialogOpen(true)}
                >
                  <Plus className="mr-1 h-4 w-4" />
                  Создать подзадачу
                </Button>
              )}

              {/* Timestamps */}
              <div className="text-xs text-muted-foreground space-y-1 pt-2">
                <p>Создано: {formatDateTime(task.created_at)}</p>
                <p>Обновлено: {formatDateTime(task.updated_at)}</p>
              </div>
            </CardContent>
          </Card>

          {/* History */}
          <Card>
            <CardHeader className="pb-2">
              <button
                className="flex items-center gap-2 text-base font-semibold w-full text-left"
                onClick={() => setShowHistory(!showHistory)}
              >
                <History className="h-4 w-4" />
                История ({task.history?.length ?? 0})
                <ChevronRight className={`h-4 w-4 ml-auto transition-transform ${showHistory ? 'rotate-90' : ''}`} />
              </button>
            </CardHeader>
            {showHistory && (
              <CardContent>
                <div className="space-y-2">
                  {task.history?.map((event) => (
                    <div key={event.id} className="flex items-start gap-2 text-xs">
                      <div className="h-1.5 w-1.5 rounded-full bg-muted-foreground mt-1.5 shrink-0" />
                      <div>
                        <span className="text-muted-foreground">
                          {TASK_EVENT_LABELS[event.event_type] ?? event.event_type}
                        </span>
                        <span className="text-muted-foreground/60 ml-2">
                          {formatRelative(event.at)}
                        </span>
                      </div>
                    </div>
                  ))}
                  {(!task.history || task.history.length === 0) && (
                    <p className="text-xs text-muted-foreground">Нет истории</p>
                  )}
                </div>
              </CardContent>
            )}
          </Card>
        </div>
      </div>

      <TaskFormDialog
        open={subDialogOpen}
        onOpenChange={setSubDialogOpen}
        parentId={task.id}
        defaultType={task.type === 'GOAL' ? 'EPIC' : task.type === 'EPIC' ? 'TASK' : 'SUBTASK'}
      />
    </div>
  );
}
