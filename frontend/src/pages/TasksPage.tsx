import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LayoutGrid, List, Plus, Inbox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { TaskCard } from '@/components/tasks/TaskCard';
import { TaskFilters } from '@/components/tasks/TaskFilters';
import { TaskFormDialog } from '@/components/tasks/TaskFormDialog';
import { getTasks } from '@/api/tasks';
import type { TaskFilters as TFilters } from '@/types';

export default function TasksPage() {
  const [filters, setFilters] = useState<TFilters>({});
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: tasks, isLoading } = useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => getTasks(filters),
  });

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <TaskFilters filters={filters} onChange={setFilters} />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex rounded-md border">
            <Button
              variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
              size="icon"
              className="rounded-r-none h-9"
              onClick={() => setViewMode('grid')}
            >
              <LayoutGrid className="h-4 w-4" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="icon"
              className="rounded-l-none h-9"
              onClick={() => setViewMode('list')}
            >
              <List className="h-4 w-4" />
            </Button>
          </div>
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Создать
          </Button>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className={viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4' : 'space-y-2'}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className={viewMode === 'grid' ? 'h-44' : 'h-14'} />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && tasks?.length === 0 && (
        <div className="text-center py-16">
          <Inbox className="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-medium mb-1">Задач не найдено</h3>
          <p className="text-sm text-muted-foreground mb-4">
            Попробуйте изменить фильтры или создайте новую задачу
          </p>
          <Button onClick={() => setDialogOpen(true)}>
            <Plus className="mr-1 h-4 w-4" />
            Создать задачу
          </Button>
        </div>
      )}

      {/* Task grid/list */}
      {!isLoading && tasks && tasks.length > 0 && (
        viewMode === 'grid' ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        ) : (
          <div className="space-y-1">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} compact />
            ))}
          </div>
        )
      )}

      <TaskFormDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
