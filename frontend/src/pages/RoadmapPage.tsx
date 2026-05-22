import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { TreePine, Target, Calendar } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { TaskTree } from '@/components/tasks/TaskTree';
import { getTaskTree } from '@/api/tasks';
import { formatDateShort } from '@/lib/dateUtils';
import type { Task } from '@/types';

function TimelineView({ tasks }: { tasks: Task[] }) {
  // Simplified timeline: show goals and epics as horizontal bars
  const allItems: Task[] = [];
  tasks.forEach((goal) => {
    allItems.push(goal);
    if (goal.children) {
      goal.children.forEach((epic) => allItems.push(epic));
    }
  });

  if (allItems.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Target className="mx-auto h-12 w-12 mb-4 opacity-50" />
        <p>Нет стратегических целей</p>
      </div>
    );
  }

  return (
    <div className="space-y-2 overflow-x-auto">
      {/* Header */}
      <div className="flex items-center text-xs text-muted-foreground border-b pb-2 mb-4 min-w-[600px]">
        <div className="w-48 sm:w-64 shrink-0 font-medium">Задача</div>
        <div className="flex-1 flex justify-between px-4">
          <span>Кв. 1</span>
          <span>Кв. 2</span>
          <span>Кв. 3</span>
          <span>Кв. 4</span>
        </div>
        <div className="w-20 text-right">Прогресс</div>
      </div>

      {allItems.map((item) => {
        const isGoal = item.type === 'GOAL';
        // Calculate simple position (0-100% of year width)
        const startPct = Math.max(0, Math.min(100, Math.random() * 30 + (isGoal ? 0 : 10)));
        const widthPct = Math.max(15, Math.min(80, 20 + item.progress * 0.4 + (isGoal ? 20 : 0)));

        return (
          <div
            key={item.id}
            className={`flex items-center gap-2 rounded-md p-2 hover:bg-accent/50 transition-colors min-w-[600px] ${
              isGoal ? '' : 'ml-6'
            }`}
          >
            <div className="w-48 sm:w-64 shrink-0 flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] shrink-0">
                {item.type === 'GOAL' ? 'Цель' : 'Эпик'}
              </Badge>
              <span className={`text-sm truncate ${isGoal ? 'font-semibold' : ''}`}>
                {item.title}
              </span>
            </div>
            <div className="flex-1 relative h-8">
              {/* Quarter lines */}
              <div className="absolute inset-0 flex">
                {[0, 1, 2, 3].map((q) => (
                  <div key={q} className="flex-1 border-l border-dashed border-border/50" />
                ))}
              </div>
              {/* Bar */}
              <div
                className="absolute top-1 h-6 rounded-md flex items-center px-2 text-[10px] text-white font-medium overflow-hidden"
                style={{
                  left: `${startPct}%`,
                  width: `${widthPct}%`,
                  background: `linear-gradient(90deg, ${
                    item.status === 'DONE' ? '#059669' :
                    item.status === 'OVERDUE' ? '#e11d48' :
                    item.status === 'IN_PROGRESS' ? '#2563eb' :
                    item.status === 'REVIEW' ? '#d97706' : '#64748b'
                  } ${item.progress}%, rgba(0,0,0,0.15) ${item.progress}%)`,
                }}
              >
                {item.progress > 20 && `${item.progress}%`}
              </div>
            </div>
            <div className="w-20 text-right">
              <span className="text-xs text-muted-foreground">
                {item.due_date ? formatDateShort(item.due_date) : ''}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function RoadmapPage() {
  const [viewMode, setViewMode] = useState<'tree' | 'timeline'>('tree');

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks', 'tree'],
    queryFn: () => getTaskTree(),
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="flex rounded-md border">
          <Button
            variant={viewMode === 'tree' ? 'secondary' : 'ghost'}
            size="sm"
            className="rounded-r-none"
            onClick={() => setViewMode('tree')}
          >
            <TreePine className="mr-1.5 h-4 w-4" />
            Дерево
          </Button>
          <Button
            variant={viewMode === 'timeline' ? 'secondary' : 'ghost'}
            size="sm"
            className="rounded-l-none"
            onClick={() => setViewMode('timeline')}
          >
            <Calendar className="mr-1.5 h-4 w-4" />
            Таймлайн
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-14 w-full" />
          ))}
        </div>
      ) : viewMode === 'tree' ? (
        <TaskTree tasks={tasks ?? []} />
      ) : (
        <Card>
          <CardContent className="p-4">
            <TimelineView tasks={tasks ?? []} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
