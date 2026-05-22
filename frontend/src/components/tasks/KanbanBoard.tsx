import { useMemo } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  useDroppable,
  closestCorners,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Target, Mountain, ListTodo, CheckSquare, Calendar } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  STATUS_LABELS,
  STATUS_COLORS,
  PRIORITY_LABELS,
  PRIORITY_COLORS,
} from '@/lib/statusUtils';
import { formatDateShort } from '@/lib/dateUtils';
import type { Task, Status, TaskType } from '@/types';

const COLUMNS: Status[] = ['NEW', 'IN_PROGRESS', 'REVIEW', 'DONE', 'OVERDUE'];

const typeIcons: Record<TaskType, React.ElementType> = {
  GOAL: Target,
  EPIC: Mountain,
  TASK: ListTodo,
  SUBTASK: CheckSquare,
};

interface SortableTaskProps {
  task: Task;
}

function SortableTask({ task }: SortableTaskProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
    data: { task },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const TypeIcon = typeIcons[task.type];
  const priorityColor = PRIORITY_COLORS[task.priority];
  const assigneeName = task.assignee_name ?? task.assignee?.full_name ?? null;
  const initials = assigneeName
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2);

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="rounded-lg border bg-card p-3 mb-2 cursor-grab active:cursor-grabbing hover:shadow-md transition-shadow"
    >
      <Link to={`/tasks/${task.id}`} className="block" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start gap-2 mb-2">
          <TypeIcon className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
          <span className="text-sm font-medium leading-tight line-clamp-2 flex-1">{task.title}</span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <Badge className={`${priorityColor.text} ${priorityColor.bg} border-0 text-[10px] px-1.5 py-0`}>
            {PRIORITY_LABELS[task.priority]}
          </Badge>
          {task.due_date && (
            <div className="flex items-center gap-0.5 text-muted-foreground">
              <Calendar className="h-3 w-3" />
              <span className="text-[10px]">{formatDateShort(task.due_date)}</span>
            </div>
          )}
          <div className="flex-1" />
          {assigneeName && (
            <Avatar className="h-5 w-5">
              <AvatarFallback className="text-[9px] bg-primary/10">{initials}</AvatarFallback>
            </Avatar>
          )}
        </div>
      </Link>
    </div>
  );
}

/**
 * A whole column registered as a droppable (id = its status). This is what
 * makes dropping a card onto an *empty* column work: with only sortable
 * items registered, an empty column had no drop target and the card snapped
 * back. Now `over.id` resolves to the column status even with zero cards.
 */
function DroppableColumn({
  status,
  isEmpty,
  children,
}: {
  status: Status;
  isEmpty: boolean;
  children: React.ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <div
      ref={setNodeRef}
      className={`flex w-72 shrink-0 flex-col rounded-lg bg-muted/50 border transition-shadow ${
        isOver ? 'ring-2 ring-primary/60' : ''
      } ${isEmpty ? 'min-h-[120px]' : ''}`}
    >
      {children}
    </div>
  );
}

interface KanbanBoardProps {
  tasks: Task[];
  onStatusChange: (taskId: string, newStatus: Status) => void;
}

export function KanbanBoard({ tasks, onStatusChange }: KanbanBoardProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }));

  const columns = useMemo(() => {
    const map: Record<Status, Task[]> = {
      NEW: [],
      IN_PROGRESS: [],
      REVIEW: [],
      DONE: [],
      OVERDUE: [],
    };
    tasks.forEach((t) => {
      if (map[t.status]) map[t.status].push(t);
    });
    return map;
  }, [tasks]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = event;
    if (!over) return;

    const taskId = active.id as string;
    const overId = over.id as string;

    // Check if dropped on a column header
    if (COLUMNS.includes(overId as Status)) {
      const task = tasks.find((t) => t.id === taskId);
      if (task && task.status !== overId) {
        onStatusChange(taskId, overId as Status);
      }
      return;
    }

    // Dropped on another task -- infer column from the target task
    const targetTask = tasks.find((t) => t.id === overId);
    if (targetTask) {
      const task = tasks.find((t) => t.id === taskId);
      if (task && task.status !== targetTask.status) {
        onStatusChange(taskId, targetTask.status);
      }
    }
  };

  const activeTask = activeId ? tasks.find((t) => t.id === activeId) : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-4 -mx-4 px-4 sm:mx-0 sm:px-0" style={{ minHeight: 'calc(100vh - 220px)' }}>
        {COLUMNS.map((status) => {
          const col = columns[status];
          const statusStyle = STATUS_COLORS[status];
          return (
            <DroppableColumn key={status} status={status} isEmpty={col.length === 0}>
              <div className="flex items-center gap-2 p-3 border-b">
                <div className={`h-2.5 w-2.5 rounded-full ${statusStyle.dot}`} />
                <h3 className="text-sm font-semibold">{STATUS_LABELS[status]}</h3>
                <Badge variant="secondary" className="ml-auto text-[11px]">
                  {col.length}
                </Badge>
              </div>
              <ScrollArea className="flex-1 p-2">
                <SortableContext
                  items={col.map((t) => t.id)}
                  strategy={verticalListSortingStrategy}
                  id={status}
                >
                  {col.map((task) => (
                    <SortableTask key={task.id} task={task} />
                  ))}
                </SortableContext>
                {col.length === 0 && (
                  <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
                    Перетащите сюда
                  </div>
                )}
              </ScrollArea>
            </DroppableColumn>
          );
        })}
      </div>

      <DragOverlay>
        {activeTask && (
          <div className="rounded-lg border bg-card p-3 shadow-lg w-72 rotate-2">
            <span className="text-sm font-medium">{activeTask.title}</span>
          </div>
        )}
      </DragOverlay>
    </DndContext>
  );
}
