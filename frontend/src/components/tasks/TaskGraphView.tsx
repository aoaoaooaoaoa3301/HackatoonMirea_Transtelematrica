import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Maximize2, ZoomIn, ZoomOut, RotateCcw, Mail, Phone, X, Search, Send, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { STATUS_LABELS } from '@/lib/statusUtils';
import { getTask, addComment } from '@/api/tasks';
import { parseServerDate } from '@/lib/dateUtils';
import { useAuthStore } from '@/store/authStore';
import type { Task, TaskType, Status } from '@/types';

// ──────────────────────── layout constants ────────────────────────
// One column per task type. Columns are at fixed X positions; cards
// inside a column have fixed width. Row 0 sits at the top, rows grow
// downward. The DFS placement algorithm assigns (col, row) to every
// visible task — siblings stack, descendants of long ancestors push
// the next sibling further down.

const COL_X: Record<TaskType, number> = {
  GOAL: 60,
  EPIC: 360,
  TASK: 660,
  SUBTASK: 960,
};

const COL_ORDER: TaskType[] = ['GOAL', 'EPIC', 'TASK', 'SUBTASK'];

const COL_LABEL: Record<TaskType, string> = {
  GOAL: 'Стратегические цели',
  EPIC: 'Эпики',
  TASK: 'Задачи',
  SUBTASK: 'Подзадачи',
};

const COL_LABEL_SHORT: Record<TaskType, string> = {
  GOAL: 'Цели',
  EPIC: 'Эпики',
  TASK: 'Задачи',
  SUBTASK: 'Подзадачи',
};

const CARD_WIDTH = 250;
const CARD_HEIGHT = 92;
const ROW_GAP = 18;
const ROW_HEIGHT = CARD_HEIGHT + ROW_GAP;

const TYPE_ACCENT: Record<TaskType, string> = {
  GOAL: '#8B5CF6',
  EPIC: '#3B82F6',
  TASK: '#06B6D4',
  SUBTASK: '#64748B',
};

const STATUS_DOT: Record<Status, string> = {
  NEW: '#A78BFA',
  IN_PROGRESS: '#3B82F6',
  REVIEW: '#06B6D4',
  DONE: '#10B981',
  OVERDUE: '#EF4444',
};

// ──────────────────────── helpers ────────────────────────

function initials(name?: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase();
}

interface Placed {
  task: Task;
  col: number; // 0..3
  row: number;
}

interface LayoutResult {
  placed: Map<string, Placed>;
  maxRowByCol: number[];
  visibleIds: Set<string>;
}

/**
 * DFS placement: for each GOAL, place it, then recurse into expanded
 * descendants. Each placement reserves a row at its column. Children
 * start at the row of their parent (or wherever the column is up to,
 * whichever is later) — keeps the visual cascade going down-right.
 */
function layoutTasks(tasks: Task[], expanded: Set<string>): LayoutResult {
  const taskById = new Map(tasks.map((t) => [t.id, t]));
  const childrenOf = new Map<string, Task[]>();
  tasks.forEach((t) => {
    if (!t.parent_id) return;
    if (!childrenOf.has(t.parent_id)) childrenOf.set(t.parent_id, []);
    childrenOf.get(t.parent_id)!.push(t);
  });

  const placed = new Map<string, Placed>();
  const visibleIds = new Set<string>();
  // Per-column row cursor — the lowest free row in that column so far.
  const rowCursor: Record<TaskType, number> = { GOAL: 0, EPIC: 0, TASK: 0, SUBTASK: 0 };

  function place(task: Task, hint: number): number {
    const myCol = COL_ORDER.indexOf(task.type);
    if (myCol < 0) return hint;
    const myRow = Math.max(hint, rowCursor[task.type]);
    placed.set(task.id, { task, col: myCol, row: myRow });
    visibleIds.add(task.id);
    rowCursor[task.type] = myRow + 1;

    if (expanded.has(task.id)) {
      const kids = (childrenOf.get(task.id) ?? []).filter((c) =>
        COL_ORDER.includes(c.type)
      );
      let childHint = myRow;
      kids.forEach((kid) => {
        childHint = place(kid, childHint);
      });
    }

    return myRow + 1;
  }

  const goals = tasks
    .filter((t) => t.type === 'GOAL')
    .sort((a, b) => a.title.localeCompare(b.title));
  let nextRow = 0;
  goals.forEach((g) => {
    nextRow = place(g, nextRow);
  });

  // Suppress unused-variable warning
  void taskById;

  const maxRowByCol = COL_ORDER.map((t) => rowCursor[t]);
  return { placed, maxRowByCol, visibleIds };
}

function bezierEdge(from: Placed, to: Placed): string {
  const x1 = COL_X[from.task.type] + CARD_WIDTH;
  const y1 = from.row * ROW_HEIGHT + CARD_HEIGHT / 2;
  const x2 = COL_X[to.task.type];
  const y2 = to.row * ROW_HEIGHT + CARD_HEIGHT / 2;
  const cx = (x1 + x2) / 2;
  return `M ${x1},${y1} C ${cx},${y1} ${cx},${y2} ${x2},${y2}`;
}

// ──────────────────────── card ────────────────────────

interface CardProps {
  placed: Placed;
  hasChildren: boolean;
  isExpanded: boolean;
  isInChain: boolean;
  isSelected: boolean;
  isHovered: boolean;
  isDimmed: boolean;
  appearDelay: number;
  onToggle: () => void;
  onSelect: () => void;
  onHover: (id: string | null) => void;
}

function TaskNodeCard({
  placed,
  hasChildren,
  isExpanded,
  isInChain,
  isSelected,
  isHovered,
  isDimmed,
  appearDelay,
  onToggle,
  onSelect,
  onHover,
}: CardProps) {
  const task = placed.task;
  const navigate = useNavigate();
  const [contactOpen, setContactOpen] = useState(false);

  const accent = TYPE_ACCENT[task.type];
  const statusColor = STATUS_DOT[task.status];

  return (
    <foreignObject
      x={COL_X[task.type]}
      y={placed.row * ROW_HEIGHT}
      width={CARD_WIDTH}
      height={CARD_HEIGHT}
      style={{ overflow: 'visible' }}
    >
      <div
        data-node-id={task.id}
        className="rounded-lg border bg-card"
        style={{
          width: CARD_WIDTH,
          height: CARD_HEIGHT,
          borderLeftWidth: 3,
          borderLeftColor: accent,
          background: `linear-gradient(135deg, ${accent}0F 0%, hsl(var(--card)) 55%)`,
          boxShadow: isSelected
            ? `0 0 0 2px ${accent}, 0 10px 28px ${accent}60`
            : isHovered
            ? `0 0 0 2px ${accent}, 0 8px 22px ${accent}50`
            : isInChain
            ? `0 0 0 1.5px ${accent}, 0 4px 12px ${accent}30`
            : '0 1px 2px rgba(0,0,0,0.18)',
          opacity: isDimmed ? 0.18 : 1,
          cursor: 'pointer',
          transform: isHovered || isSelected ? 'translateY(-2px)' : 'translateY(0)',
          transition: `transform 180ms cubic-bezier(.2,.7,.3,1), box-shadow 200ms ease, opacity 200ms ease, background 200ms ease`,
          animation: `ttm-card-in 320ms cubic-bezier(.2,.7,.3,1) ${appearDelay}ms both`,
        }}
        onMouseEnter={() => onHover(task.id)}
        onMouseLeave={() => onHover(null)}
        onClick={(e) => {
          e.stopPropagation();
          onSelect();
        }}
        onDoubleClick={(e) => {
          e.stopPropagation();
          navigate(`/tasks/${task.id}`);
        }}
        onContextMenu={(e) => {
          e.preventDefault();
          navigate(`/tasks/${task.id}`);
        }}
      >
        <div className="flex flex-col h-full px-3 py-2 gap-1">
          {/* Title row */}
          <div className="flex items-start gap-1.5">
            <span
              className="inline-block h-2 w-2 rounded-full shrink-0 mt-1.5"
              style={{ backgroundColor: statusColor }}
              title={STATUS_LABELS[task.status]}
            />
            <div className="flex-1 text-[12.5px] font-semibold leading-tight line-clamp-2">
              {task.title}
            </div>
            {hasChildren && (
              <button
                className="shrink-0 h-5 w-5 rounded text-[11px] font-bold text-white flex items-center justify-center"
                style={{ backgroundColor: accent }}
                onClick={(e) => {
                  e.stopPropagation();
                  onToggle();
                }}
                title={isExpanded ? 'Свернуть' : 'Раскрыть подзадачи'}
              >
                {isExpanded ? '−' : '+'}
              </button>
            )}
          </div>

          {/* Assignee + dept */}
          <div className="flex items-center gap-1.5 text-[10.5px]">
            {task.assignee_name ? (
              <Popover open={contactOpen} onOpenChange={setContactOpen}>
                <PopoverTrigger asChild>
                  <button
                    className="flex items-center gap-1.5 hover:bg-muted/60 rounded px-1 -ml-1 min-w-0"
                    onClick={(e) => e.stopPropagation()}
                    title="Контакты"
                  >
                    <Avatar className="h-5 w-5 shrink-0">
                      <AvatarFallback
                        className="text-[9px] font-medium"
                        style={{ backgroundColor: `${accent}30`, color: accent }}
                      >
                        {initials(task.assignee_name)}
                      </AvatarFallback>
                    </Avatar>
                    <span className="truncate text-muted-foreground">
                      {task.assignee_name}
                    </span>
                  </button>
                </PopoverTrigger>
                <PopoverContent
                  side="right"
                  align="start"
                  className="w-64 p-3"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="flex items-center gap-2 mb-2">
                    <Avatar className="h-8 w-8">
                      <AvatarFallback
                        className="text-xs font-medium"
                        style={{ backgroundColor: `${accent}30`, color: accent }}
                      >
                        {initials(task.assignee_name)}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <div className="text-sm font-semibold leading-tight">
                        {task.assignee_name}
                      </div>
                      {task.assigned_department_name && (
                        <div className="text-[10px] text-muted-foreground">
                          {task.assigned_department_name}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className="space-y-1 text-xs">
                    <a
                      href={`mailto:${(task.assignee_name ?? '').toLowerCase().replace(/\s+/g, '.')}@ttm.local`}
                      className="flex items-center gap-2 text-muted-foreground hover:text-primary"
                    >
                      <Mail className="h-3 w-3" />
                      {(task.assignee_name ?? '').toLowerCase().replace(/\s+/g, '.')}@ttm.local
                    </a>
                    <a
                      href="tel:+74955892412"
                      className="flex items-center gap-2 text-muted-foreground hover:text-primary"
                    >
                      <Phone className="h-3 w-3" />
                      +7 (495) 589-24-12 (доб. 100)
                    </a>
                  </div>
                </PopoverContent>
              </Popover>
            ) : (
              <span className="text-muted-foreground italic">не назначен</span>
            )}
          </div>

          {/* Dept badge + progress */}
          <div className="flex items-center justify-between gap-2 mt-auto text-[10px]">
            {task.assigned_department_name ? (
              <Badge variant="outline" className="text-[9px] px-1.5 py-0">
                {task.assigned_department_name}
              </Badge>
            ) : <span />}
            <div className="flex items-center gap-1.5 shrink-0">
              <div className="h-1 w-12 rounded-full bg-muted overflow-hidden">
                <div
                  className="h-full"
                  style={{
                    width: `${task.progress}%`,
                    backgroundColor: accent,
                  }}
                />
              </div>
              <span className="text-muted-foreground w-7 text-right">
                {task.progress}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </foreignObject>
  );
}

// ──────────────────────── overview panel ────────────────────────
// Right-side detail panel — shows everything about the selected task
// in one place: type/status header, description, meta, the parent
// chain (with assignees), and direct subtasks (clickable to drill).

interface OverviewPanelProps {
  task: Task;
  chain: Task[]; // root → … → selected (inclusive)
  children: Task[];
  onClose: () => void;
  onSelectChild: (id: string) => void;
  onOpen: () => void;
}

function TaskOverviewPanel({
  task,
  chain,
  children,
  onClose,
  onSelectChild,
  onOpen,
}: OverviewPanelProps) {
  const accent = TYPE_ACCENT[task.type];
  const statusColor = STATUS_DOT[task.status];
  const ancestors = chain.filter((t) => t.id !== task.id);
  const currentUser = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const [commentBody, setCommentBody] = useState('');
  const commentsScrollRef = useRef<HTMLDivElement>(null);

  // Fetch full task detail (includes comments + history) when this
  // panel mounts or the selected task changes.
  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['task-detail', task.id],
    queryFn: () => getTask(task.id),
  });

  const postComment = useMutation({
    mutationFn: (body: string) => addComment(task.id, body),
    onSuccess: () => {
      setCommentBody('');
      qc.invalidateQueries({ queryKey: ['task-detail', task.id] });
      // scroll to bottom of comments after refetch
      setTimeout(() => {
        commentsScrollRef.current?.scrollTo({
          top: commentsScrollRef.current.scrollHeight,
          behavior: 'smooth',
        });
      }, 250);
    },
  });

  const comments = detail?.comments ?? [];

  const daysLeft = task.due_date
    ? Math.ceil(
        (new Date(task.due_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24)
      )
    : null;

  const submitComment = () => {
    const body = commentBody.trim();
    if (!body || postComment.isPending) return;
    postComment.mutate(body);
  };

  return (
    <div
      className="absolute top-[58px] right-3 bottom-3 left-3 sm:left-auto w-auto sm:w-[340px] z-20 rounded-lg border bg-background/97 backdrop-blur shadow-2xl flex flex-col"
      style={{
        animation: 'ttm-panel-in 280ms cubic-bezier(.2,.7,.3,1) both',
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 border-b flex items-start justify-between gap-2"
        style={{
          background: `linear-gradient(135deg, ${accent}18 0%, transparent 100%)`,
        }}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1.5">
            <Badge
              variant="outline"
              className="text-[10px] py-0"
              style={{ borderColor: `${accent}80`, color: accent }}
            >
              {COL_LABEL_SHORT[task.type]}
            </Badge>
            <Badge
              className="text-[10px] py-0 border-0 text-white"
              style={{ backgroundColor: statusColor }}
            >
              {STATUS_LABELS[task.status]}
            </Badge>
          </div>
          <h3 className="text-base font-semibold leading-tight">{task.title}</h3>
        </div>
        <button
          className="p-1 -m-1 rounded hover:bg-muted shrink-0"
          onClick={onClose}
          aria-label="Закрыть"
        >
          <X className="h-4 w-4 text-muted-foreground" />
        </button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {task.description && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
              Описание
            </div>
            <p className="text-xs leading-relaxed">{task.description}</p>
          </div>
        )}

        {/* Meta grid */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          {task.assignee_name && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                Исполнитель
              </div>
              <div className="flex items-center gap-1.5 min-w-0">
                <Avatar className="h-5 w-5 shrink-0">
                  <AvatarFallback
                    className="text-[9px] font-medium"
                    style={{ backgroundColor: `${accent}30`, color: accent }}
                  >
                    {initials(task.assignee_name)}
                  </AvatarFallback>
                </Avatar>
                <span className="truncate">{task.assignee_name}</span>
              </div>
            </div>
          )}
          {task.assigned_department_name && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                Отдел
              </div>
              <div className="truncate">{task.assigned_department_name}</div>
            </div>
          )}
          {task.start_date && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                Старт
              </div>
              <div>{new Date(task.start_date).toLocaleDateString('ru-RU')}</div>
            </div>
          )}
          {task.due_date && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">
                Дедлайн
              </div>
              <div className="flex flex-col">
                <span>{new Date(task.due_date).toLocaleDateString('ru-RU')}</span>
                {daysLeft !== null && (
                  <span
                    className={
                      daysLeft < 0
                        ? 'text-rose-500 text-[10px]'
                        : daysLeft <= 3
                        ? 'text-amber-500 text-[10px]'
                        : 'text-muted-foreground text-[10px]'
                    }
                  >
                    {daysLeft < 0
                      ? `просрочено на ${-daysLeft} дн.`
                      : daysLeft === 0
                      ? 'сегодня'
                      : `осталось ${daysLeft} дн.`}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Progress */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
              Прогресс
            </span>
            <span className="text-xs font-semibold">{task.progress}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full transition-all"
              style={{
                width: `${task.progress}%`,
                backgroundColor: accent,
              }}
            />
          </div>
        </div>

        {/* Parent chain */}
        {ancestors.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
              Откуда родилась эта задача
            </div>
            <div className="space-y-1">
              {ancestors.map((t, i) => (
                <button
                  key={t.id}
                  className="w-full flex items-center gap-2 text-xs px-2 py-1.5 rounded hover:bg-muted text-left"
                  onClick={() => onSelectChild(t.id)}
                >
                  <span
                    className="text-[9px] font-medium px-1.5 py-0.5 rounded shrink-0"
                    style={{
                      backgroundColor: `${TYPE_ACCENT[t.type]}25`,
                      color: TYPE_ACCENT[t.type],
                    }}
                  >
                    {COL_LABEL_SHORT[t.type]}
                  </span>
                  <span className="truncate flex-1 font-medium">{t.title}</span>
                  {t.assignee_name && (
                    <span className="text-muted-foreground truncate text-[10px]">
                      {t.assignee_name.split(' ')[0]}
                    </span>
                  )}
                  {i < ancestors.length - 1 && (
                    <span className="text-muted-foreground">↓</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Direct children */}
        {children.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
              Подзадачи ({children.length})
            </div>
            <div className="space-y-1">
              {children.map((c) => (
                <button
                  key={c.id}
                  className="w-full flex items-center gap-2 text-xs px-2 py-1.5 rounded hover:bg-muted text-left"
                  onClick={() => onSelectChild(c.id)}
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full shrink-0"
                    style={{ backgroundColor: STATUS_DOT[c.status] }}
                  />
                  <span className="truncate flex-1">{c.title}</span>
                  <span className="text-muted-foreground text-[10px] shrink-0">
                    {c.progress}%
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Comments thread */}
        <div>
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">
            <MessageSquare className="h-3 w-3" />
            <span>Обсуждение{detail ? ` (${comments.length})` : ''}</span>
          </div>

          <div
            ref={commentsScrollRef}
            className="max-h-72 overflow-y-auto pr-1 space-y-2"
          >
            {detailLoading && (
              <div className="space-y-2">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-3/4" />
              </div>
            )}

            {!detailLoading && comments.length === 0 && (
              <div className="text-xs text-muted-foreground italic py-2">
                Пока никто не написал. Будь первым — задай вопрос или
                поделись статусом.
              </div>
            )}

            {!detailLoading &&
              comments.map((c) => {
                const isMine = currentUser?.id === c.author_id;
                const authorName =
                  c.author?.full_name ??
                  (isMine ? currentUser?.full_name : null) ??
                  'Сотрудник';
                const time = parseServerDate(c.created_at).toLocaleString('ru-RU', {
                  day: '2-digit',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                });
                return (
                  <div
                    key={c.id}
                    className="text-xs rounded-md border bg-card/60 p-2"
                    style={{
                      borderLeft: `2px solid ${isMine ? accent : '#64748B'}`,
                      animation: 'ttm-comment-in 240ms ease both',
                    }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <Avatar className="h-4 w-4">
                        <AvatarFallback
                          className="text-[8px] font-medium"
                          style={{
                            backgroundColor: isMine ? `${accent}30` : '#64748B30',
                            color: isMine ? accent : '#64748B',
                          }}
                        >
                          {initials(authorName)}
                        </AvatarFallback>
                      </Avatar>
                      <span className="font-medium truncate">{authorName}</span>
                      <span className="text-muted-foreground text-[10px] ml-auto shrink-0">
                        {time}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed whitespace-pre-wrap break-words">
                      {c.body}
                    </p>
                  </div>
                );
              })}
          </div>

          {/* Composer */}
          <div className="mt-2 flex gap-1 items-end">
            <Textarea
              value={commentBody}
              onChange={(e) => setCommentBody(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  submitComment();
                }
              }}
              placeholder="Написать сообщение… (Cmd+Enter)"
              rows={2}
              className="text-xs resize-none min-h-[44px]"
            />
            <Button
              size="icon"
              className="shrink-0 h-9 w-9"
              disabled={!commentBody.trim() || postComment.isPending}
              onClick={submitComment}
              aria-label="Отправить"
            >
              <Send className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t">
        <Button size="sm" className="w-full" onClick={onOpen}>
          Открыть полную карточку →
        </Button>
      </div>
    </div>
  );
}

// ──────────────────────── main component ────────────────────────

export function TaskGraphView({ tasks }: { tasks: Task[] }) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [dims, setDims] = useState({ w: 1200, h: 700 });

  // Default-expand all GOALs so EPICs are visible immediately
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    return new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id));
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchQ, setSearchQ] = useState('');

  // Pan + zoom
  const [transform, setTransform] = useState({ x: 20, y: 12, k: 0.85 });
  const panStateRef = useRef({ dragging: false, sx: 0, sy: 0, ox: 0, oy: 0 });

  // Resize
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setDims({ w: el.clientWidth, h: Math.max(560, el.clientHeight) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Re-init expanded when tasks change
  useEffect(() => {
    if (expanded.size === 0 && tasks.length > 0) {
      setExpanded(new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks]);

  // Layout + relationship helpers. The graph view leans on three derived
  // structures: parent_chain (id → ancestors up to GOAL),
  // descendantsOf (id → entire subtree below), and childrenOf (direct only).
  // These power the "click a goal → light up its whole branch, fade
  // everything else" behaviour.
  const { placed, maxRowByCol, hasChildrenOf, parentChainOf, descendantsOf, directChildrenOf } = useMemo(() => {
    const layoutOut = layoutTasks(tasks, expanded);
    const childrenByParent = new Map<string, Task[]>();
    tasks.forEach((t) => {
      if (t.parent_id) {
        if (!childrenByParent.has(t.parent_id)) childrenByParent.set(t.parent_id, []);
        childrenByParent.get(t.parent_id)!.push(t);
      }
    });
    const taskById = new Map(tasks.map((t) => [t.id, t]));
    const chainCache = new Map<string, Set<string>>();
    const descCache = new Map<string, Set<string>>();
    function chainFor(id: string): Set<string> {
      if (chainCache.has(id)) return chainCache.get(id)!;
      const chain = new Set<string>();
      let cur: Task | undefined = taskById.get(id);
      while (cur) {
        chain.add(cur.id);
        cur = cur.parent_id ? taskById.get(cur.parent_id) : undefined;
      }
      chainCache.set(id, chain);
      return chain;
    }
    function descFor(id: string): Set<string> {
      if (descCache.has(id)) return descCache.get(id)!;
      const out = new Set<string>([id]);
      const stack = [id];
      while (stack.length) {
        const cur = stack.pop()!;
        (childrenByParent.get(cur) ?? []).forEach((c) => {
          if (!out.has(c.id)) {
            out.add(c.id);
            stack.push(c.id);
          }
        });
      }
      descCache.set(id, out);
      return out;
    }
    return {
      placed: layoutOut.placed,
      maxRowByCol: layoutOut.maxRowByCol,
      hasChildrenOf: (id: string) => (childrenByParent.get(id)?.length ?? 0) > 0,
      parentChainOf: chainFor,
      descendantsOf: descFor,
      directChildrenOf: (id: string) => childrenByParent.get(id) ?? [],
    };
  }, [tasks, expanded]);

  const placedList = useMemo(() => Array.from(placed.values()), [placed]);

  // Edges
  const edges = useMemo(() => {
    const out: { src: Placed; dst: Placed }[] = [];
    placedList.forEach((p) => {
      if (!p.task.parent_id) return;
      const parent = placed.get(p.task.parent_id);
      if (!parent) return;
      out.push({ src: parent, dst: p });
    });
    return out;
  }, [placedList, placed]);

  // Highlighted chain (ancestors of selected, OR hovered if nothing selected).
  // This means a viewer can simply mouse-over a card to instantly see the
  // chain of responsibility up to the strategic goal — no click required.
  const activeId = selectedId ?? hoveredId;
  const chain = useMemo(() => {
    if (!activeId) return new Set<string>();
    return parentChainOf(activeId);
  }, [activeId, parentChainOf]);

  // When something is *selected* (not just hovered), the focus set is
  // the union of its entire descendant subtree AND its parent chain. The
  // user clicked a GOAL → we want every mini-task underneath visible and
  // bright, plus the chain above for context. On hover-only, focus is
  // just the parent chain (lighter affordance).
  const focusSet = useMemo(() => {
    if (selectedId) {
      const out = new Set<string>(descendantsOf(selectedId));
      parentChainOf(selectedId).forEach((id) => out.add(id));
      return out;
    }
    if (hoveredId) return parentChainOf(hoveredId);
    return new Set<string>();
  }, [selectedId, hoveredId, descendantsOf, parentChainOf]);

  // Search-filtered ID set: cards whose title matches the query are pulled
  // forward, others fade. Empty query = nothing dimmed.
  const searchMatchIds = useMemo(() => {
    const q = searchQ.trim().toLowerCase();
    if (!q) return null;
    const matches = new Set<string>();
    placedList.forEach((p) => {
      if (p.task.title.toLowerCase().includes(q)) matches.add(p.task.id);
    });
    return matches;
  }, [searchQ, placedList]);

  // Content bounds for fit-to-view
  const contentBounds = useMemo(() => {
    const maxRow = Math.max(0, ...maxRowByCol);
    return {
      w: COL_X.SUBTASK + CARD_WIDTH + 40,
      h: maxRow * ROW_HEIGHT + 40,
    };
  }, [maxRowByCol]);

  const fitToView = useCallback(() => {
    const k = Math.min(
      dims.w / contentBounds.w,
      (dims.h - 56) / contentBounds.h,
      1.1
    );
    setTransform({
      x: (dims.w - contentBounds.w * k) / 2,
      y: 56 + (dims.h - 56 - contentBounds.h * k) / 2,
      k,
    });
  }, [dims, contentBounds]);

  // Fit camera to the selected subtree so the user lands on the
  // expanded branch rather than at the original viewport. Right-side
  // panel takes ~340px → reserve that space.
  const fitToSubtree = useCallback(() => {
    if (!selectedId) return;
    const ids = focusSet;
    const placedInFocus = Array.from(ids)
      .map((id) => placed.get(id))
      .filter((p): p is Placed => Boolean(p));
    if (placedInFocus.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    placedInFocus.forEach((p) => {
      const x = COL_X[p.task.type];
      const y = p.row * ROW_HEIGHT;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x + CARD_WIDTH);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y + CARD_HEIGHT);
    });
    // Padding around the focus rect
    const padX = 30, padY = 30;
    const w = maxX - minX + padX * 2;
    const h = maxY - minY + padY * 2;
    const availW = dims.w - 360; // leave room for the overview panel
    const availH = dims.h - 56 - 60;
    const k = Math.min(availW / w, availH / h, 1.0);
    setTransform({
      x: -(minX - padX) * k + 12,
      y: -(minY - padY) * k + 56 + (availH - h * k) / 2,
      k,
    });
  }, [selectedId, focusSet, placed, dims]);

  useEffect(() => {
    fitToView();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks]);

  // When selection changes, camera flies to the focused branch.
  useEffect(() => {
    if (selectedId) fitToSubtree();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // Select a task: pin it AND auto-expand its full subtree so every
  // descendant is rendered. Clicking the same task again deselects.
  const handleSelect = useCallback(
    (id: string) => {
      setSelectedId((cur) => {
        if (cur === id) return null;
        // expand the subtree under the new selection
        const desc = descendantsOf(id);
        setExpanded((prev) => {
          const next = new Set(prev);
          desc.forEach((d) => {
            if (d !== id) next.add(d);
          });
          // also expand the clicked node itself so its direct children show
          next.add(id);
          return next;
        });
        return id;
      });
    },
    [descendantsOf]
  );

  // ESC clears selection — quick exit from focus mode.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedId(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const toggleNode = useCallback((id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        // also collapse all descendants (clean up)
        const childOf = new Map<string, Task[]>();
        tasks.forEach((t) => {
          if (t.parent_id) {
            if (!childOf.has(t.parent_id)) childOf.set(t.parent_id, []);
            childOf.get(t.parent_id)!.push(t);
          }
        });
        const stack = [id];
        while (stack.length) {
          const cur = stack.pop()!;
          next.delete(cur);
          (childOf.get(cur) ?? []).forEach((c) => stack.push(c.id));
        }
      } else {
        next.add(id);
      }
      return next;
    });
  }, [tasks]);

  const expandAll = () => {
    setExpanded(new Set(tasks.filter((t) => hasChildrenOf(t.id)).map((t) => t.id)));
  };
  const collapseToGoals = () => {
    setExpanded(new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id)));
    setSelectedId(null);
  };

  // Mouse pan
  const onMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest('[data-node-id]')) return;
    if ((e.target as Element).closest('button')) return;
    panStateRef.current = {
      dragging: true,
      sx: e.clientX,
      sy: e.clientY,
      ox: transform.x,
      oy: transform.y,
    };
    setSelectedId(null);
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!panStateRef.current.dragging) return;
    const dx = e.clientX - panStateRef.current.sx;
    const dy = e.clientY - panStateRef.current.sy;
    setTransform((t) => ({
      ...t,
      x: panStateRef.current.ox + dx,
      y: panStateRef.current.oy + dy,
    }));
  };
  const onMouseUp = () => {
    panStateRef.current.dragging = false;
  };
  // Wheel zoom (native, non-passive)
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = -e.deltaY * 0.0009;
      setTransform((t) => {
        const newK = Math.max(0.35, Math.min(1.8, t.k * Math.exp(delta)));
        const rect = el.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const py = e.clientY - rect.top;
        const nx = px - (px - t.x) * (newK / t.k);
        const ny = py - (py - t.y) * (newK / t.k);
        return { x: nx, y: ny, k: newK };
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const zoomIn = () => setTransform((t) => ({ ...t, k: Math.min(1.8, t.k * 1.2) }));
  const zoomOut = () => setTransform((t) => ({ ...t, k: Math.max(0.35, t.k / 1.2) }));

  // Selected task details for the breadcrumb strip
  const selectedTask = selectedId ? placed.get(selectedId)?.task : null;
  const chainTasks = useMemo(() => {
    if (!selectedTask) return [] as Task[];
    const ids = Array.from(parentChainOf(selectedTask.id));
    const byId = new Map(tasks.map((t) => [t.id, t]));
    return ids
      .map((id) => byId.get(id))
      .filter((t): t is Task => Boolean(t))
      .sort((a, b) => COL_ORDER.indexOf(a.type) - COL_ORDER.indexOf(b.type));
  }, [selectedTask, parentChainOf, tasks]);

  return (
    <div
      ref={containerRef}
      className="relative w-full rounded-lg border bg-card/40 overflow-hidden select-none"
      style={{ height: 'min(78vh, 820px)' }}
    >
      {/* Column headers — fixed in screen space (sticky) */}
      <div className="absolute top-0 left-0 right-0 h-12 z-10 border-b bg-background/85 backdrop-blur flex">
        {COL_ORDER.map((type) => (
          <div
            key={type}
            className="flex-1 flex items-center justify-center text-xs font-semibold border-r last:border-r-0"
            style={{ color: TYPE_ACCENT[type] }}
          >
            <span className="hidden md:inline">{COL_LABEL[type]}</span>
            <span className="md:hidden">{COL_LABEL_SHORT[type]}</span>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="absolute top-[58px] left-3 z-10 flex gap-2 flex-wrap items-center">
        <Button size="sm" variant="secondary" onClick={expandAll}>
          Раскрыть всё
        </Button>
        <Button size="sm" variant="outline" onClick={collapseToGoals}>
          <RotateCcw className="mr-1 h-3 w-3" />
          Только цели
        </Button>
        <Button size="sm" variant="outline" onClick={fitToView}>
          <Maximize2 className="mr-1 h-3 w-3" />
          Уместить
        </Button>
        <div className="flex rounded-md border bg-background">
          <Button size="sm" variant="ghost" className="h-9 rounded-r-none" onClick={zoomOut}>
            <ZoomOut className="h-3 w-3" />
          </Button>
          <Button size="sm" variant="ghost" className="h-9 rounded-l-none" onClick={zoomIn}>
            <ZoomIn className="h-3 w-3" />
          </Button>
        </div>
        <div className="relative">
          <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
          <Input
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="Найти задачу…"
            className="h-9 pl-7 pr-7 w-52 text-xs"
          />
          {searchQ && (
            <button
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              onClick={() => setSearchQ('')}
              aria-label="Очистить"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>
        {searchMatchIds && (
          <span className="text-[10px] text-muted-foreground">
            найдено: {searchMatchIds.size}
          </span>
        )}
      </div>

      {/* Right-side overview panel — slides in when a card is selected.
          Shows task overview + parent chain + direct subtasks, all in
          one place so the canvas keeps focus on the highlighted branch. */}
      {selectedTask && (
        <TaskOverviewPanel
          task={selectedTask}
          chain={chainTasks}
          children={directChildrenOf(selectedTask.id)}
          onClose={() => setSelectedId(null)}
          onSelectChild={(id) => handleSelect(id)}
          onOpen={() => navigate(`/tasks/${selectedTask.id}`)}
        />
      )}

      <div
        className="absolute bottom-3 left-3 z-10 text-[10px] text-muted-foreground bg-background/80 backdrop-blur rounded px-2 py-1 pointer-events-none"
        style={{
          right: selectedTask ? 360 : 12,
          transition: 'right 250ms ease',
        }}
      >
        Наведи — цепочка наверх · Клик — раскрыть ветку и фокус · ESC — сбросить
      </div>

      {/* Animations — declared once, used by every card via inline animation */}
      <style>
        {`
          @keyframes ttm-card-in {
            from { opacity: 0; transform: translateY(8px) scale(0.96); }
            to   { opacity: 1; transform: translateY(0) scale(1); }
          }
          @keyframes ttm-pulse-ring {
            0%, 100% { box-shadow: 0 0 0 0 currentColor; }
            50%      { box-shadow: 0 0 0 6px transparent; }
          }
          @keyframes ttm-panel-in {
            from { opacity: 0; transform: translateX(12px); }
            to   { opacity: 1; transform: translateX(0); }
          }
          @keyframes ttm-comment-in {
            from { opacity: 0; transform: translateY(4px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        `}
      </style>

      {/* SVG canvas — pan/zoom is applied via transform */}
      <svg
        ref={svgRef}
        width={dims.w}
        height={dims.h}
        style={{
          cursor: panStateRef.current.dragging ? 'grabbing' : 'grab',
          display: 'block',
        }}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <g
          style={{
            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`,
            transformOrigin: '0 0',
            transition: panStateRef.current.dragging ? 'none' : 'transform 350ms cubic-bezier(.2,.7,.3,1)',
          }}
        >
          {/* Column background bands */}
          {COL_ORDER.map((type) => {
            const x = COL_X[type] - 14;
            const w = CARD_WIDTH + 28;
            const maxRow = Math.max(1, ...maxRowByCol);
            const h = maxRow * ROW_HEIGHT;
            return (
              <rect
                key={`band-${type}`}
                x={x}
                y={-10}
                width={w}
                height={h + 30}
                fill={`${TYPE_ACCENT[type]}08`}
                stroke={`${TYPE_ACCENT[type]}25`}
                strokeDasharray="2,4"
                rx={8}
              />
            );
          })}

          {/* Edges */}
          <g style={{ pointerEvents: 'none' }}>
            {edges.map(({ src, dst }, i) => {
              // An edge is "in focus" if both endpoints are in the focus
              // set (selected subtree ∪ ancestor chain, or just the
              // hover-chain). Flow particles only run on the parent
              // chain — otherwise too much animation when a whole
              // subtree is expanded.
              const inFocus =
                focusSet.has(src.task.id) && focusSet.has(dst.task.id);
              const onChain = chain.has(src.task.id) && chain.has(dst.task.id);
              const filterFade =
                searchMatchIds !== null &&
                !searchMatchIds.has(src.task.id) &&
                !searchMatchIds.has(dst.task.id);
              const isDimmed = (activeId !== null && !inFocus) || filterFade;
              const edgeKey = `${src.task.id}-${dst.task.id}`;
              const stroke = inFocus ? TYPE_ACCENT[src.task.type] : 'rgba(148,163,184,0.5)';
              return (
                <g key={`e-${edgeKey}-${i}`}>
                  <path
                    d={bezierEdge(src, dst)}
                    fill="none"
                    stroke={stroke}
                    strokeWidth={inFocus ? 2.2 : 1.4}
                    opacity={isDimmed ? 0.14 : 1}
                    style={{ transition: 'all 250ms ease' }}
                  />
                  {onChain && (
                    <>
                      <circle r={2.6} fill={stroke}>
                        <animateMotion
                          dur="1.6s"
                          repeatCount="indefinite"
                          rotate="auto"
                          path={bezierEdge(src, dst)}
                        />
                      </circle>
                      <circle r={2} fill={stroke} opacity={0.55}>
                        <animateMotion
                          dur="1.6s"
                          repeatCount="indefinite"
                          begin="0.55s"
                          rotate="auto"
                          path={bezierEdge(src, dst)}
                        />
                      </circle>
                    </>
                  )}
                </g>
              );
            })}
          </g>

          {/* Cards */}
          <g>
            {placedList.map((p, idx) => {
              const inFocus = focusSet.has(p.task.id);
              const onChain = chain.has(p.task.id);
              const matched = searchMatchIds?.has(p.task.id) ?? null;
              const filterFade = matched === false;
              const isDimmed = (activeId !== null && !inFocus) || filterFade;
              return (
                <TaskNodeCard
                  key={p.task.id}
                  placed={p}
                  hasChildren={hasChildrenOf(p.task.id)}
                  isExpanded={expanded.has(p.task.id)}
                  isInChain={
                    (onChain || inFocus) &&
                    p.task.id !== selectedId &&
                    p.task.id !== hoveredId
                  }
                  isSelected={p.task.id === selectedId}
                  isHovered={p.task.id === hoveredId}
                  isDimmed={isDimmed}
                  appearDelay={Math.min(idx * 30, 360)}
                  onToggle={() => toggleNode(p.task.id)}
                  onSelect={() => handleSelect(p.task.id)}
                  onHover={setHoveredId}
                />
              );
            })}
          </g>
        </g>
      </svg>

      {/* Empty state */}
      {placedList.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-center">
          <p className="text-sm text-muted-foreground">
            Нет стратегических целей. Создайте первую — и декомпозируйте её на эпики и задачи.
          </p>
        </div>
      )}
    </div>
  );
}
