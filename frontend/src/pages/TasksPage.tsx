import { useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { LayoutGrid, List, Plus, Inbox, Network, GitBranch, Download, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { TaskCard } from '@/components/tasks/TaskCard';
import { TaskFilters } from '@/components/tasks/TaskFilters';
import { TaskFormDialog } from '@/components/tasks/TaskFormDialog';
import { TaskStrategyView } from '@/components/tasks/TaskStrategyView';
import { TaskGraphView } from '@/components/tasks/TaskGraphView';
import { getTasks, exportTasks, importTasks } from '@/api/tasks';
import { useAuthStore } from '@/store/authStore';
import { canCreateTask } from '@/lib/permissions';
import type { TaskFilters as TFilters, Status, Priority } from '@/types';

type ViewTab = 'strategy' | 'graph' | 'list';

export default function TasksPage() {
  const user = useAuthStore((s) => s.user);
  // Allow deep-linking from the dashboard, e.g. /tasks?tab=list&status=OVERDUE.
  const [searchParams] = useSearchParams();
  const paramTab = searchParams.get('tab');
  const paramStatus = searchParams.get('status');
  const paramPriority = searchParams.get('priority');
  const paramDept = searchParams.get('department_id');
  const [tab, setTab] = useState<ViewTab>(
    paramTab === 'list' || paramTab === 'graph' || paramTab === 'strategy' ? paramTab : 'strategy'
  );
  const [filters, setFilters] = useState<TFilters>(() => {
    const init: TFilters = {};
    if (paramStatus) init.status = paramStatus.split(',') as Status[];
    if (paramPriority) init.priority = paramPriority.split(',') as Priority[];
    if (paramDept) init.department_id = paramDept;
    return init;
  });
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [dialogOpen, setDialogOpen] = useState(false);
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleExport = async () => {
    try {
      await exportTasks();
      toast.success('Файл экспортирован');
    } catch {
      toast.error('Ошибка экспорта');
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await importTasks(file);
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      if (result.errors.length > 0) {
        toast.warning(`Импортировано: ${result.created}, пропущено: ${result.skipped}`, {
          description: result.errors.slice(0, 5).map((err) => `Строка ${err.row}: ${err.message}`).join('\n'),
          duration: 8000,
        });
      } else {
        toast.success(`Импортировано: ${result.created} задач`);
      }
    } catch {
      toast.error('Ошибка импорта');
    } finally {
      e.target.value = '';
    }
  };

  // Strategy + graph tabs always fetch the full set (ignore filters — structure is the value)
  const { data: allTasks, isLoading: isLoadingAll } = useQuery({
    queryKey: ['tasks', 'all'],
    queryFn: () => getTasks({}),
    enabled: tab === 'strategy' || tab === 'graph',
  });

  // List tab uses filters
  const { data: filteredTasks, isLoading: isLoadingFiltered } = useQuery({
    queryKey: ['tasks', filters],
    queryFn: () => getTasks(filters),
    enabled: tab === 'list',
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <Tabs value={tab} onValueChange={(v) => setTab(v as ViewTab)}>
          <TabsList>
            <TabsTrigger value="strategy" className="gap-1.5 sm:gap-2">
              <Network className="h-4 w-4" />
              <span className="hidden sm:inline">По целям</span>
            </TabsTrigger>
            <TabsTrigger value="graph" className="gap-1.5 sm:gap-2">
              <GitBranch className="h-4 w-4" />
              <span className="hidden sm:inline">Граф</span>
            </TabsTrigger>
            <TabsTrigger value="list" className="gap-1.5 sm:gap-2">
              <List className="h-4 w-4" />
              <span className="hidden sm:inline">Список</span>
            </TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 sm:mr-1" />
            <span className="hidden sm:inline">Экспорт</span>
          </Button>
          {canCreateTask(user) && (
            <>
              <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                <Upload className="h-4 w-4 sm:mr-1" />
                <span className="hidden sm:inline">Импорт</span>
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={handleImport}
              />
            </>
          )}
          {canCreateTask(user) && (
            <Button className="hidden sm:inline-flex" onClick={() => setDialogOpen(true)}>
              <Plus className="h-4 w-4 sm:mr-1" />
              <span className="hidden sm:inline">Создать</span>
            </Button>
          )}
        </div>
      </div>

      {/* Strategy view: grouped by GOAL with delegation flow */}
      {tab === 'strategy' && (
        <>
          {isLoadingAll && (
            <div className="space-y-4">
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-32 w-full" />
              <Skeleton className="h-32 w-full" />
            </div>
          )}
          {!isLoadingAll && allTasks && <TaskStrategyView tasks={allTasks} />}
        </>
      )}

      {/* Graph view: force-directed, click to expand subtree */}
      {tab === 'graph' && (
        <>
          {isLoadingAll && <Skeleton className="h-[600px] w-full" />}
          {!isLoadingAll && allTasks && <TaskGraphView tasks={allTasks} />}
        </>
      )}

      {/* List view: flat with filters */}
      {tab === 'list' && (
        <>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <TaskFilters filters={filters} onChange={setFilters} />
            </div>
            <div className="flex rounded-md border shrink-0">
              <Button
                variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
                size="icon"
                className="rounded-r-none h-9"
                onClick={() => setViewMode('grid')}
                aria-label="Сетка"
              >
                <LayoutGrid className="h-4 w-4" />
              </Button>
              <Button
                variant={viewMode === 'list' ? 'secondary' : 'ghost'}
                size="icon"
                className="rounded-l-none h-9"
                onClick={() => setViewMode('list')}
                aria-label="Список"
              >
                <List className="h-4 w-4" />
              </Button>
            </div>
          </div>

          {isLoadingFiltered && (
            <div
              className={
                viewMode === 'grid'
                  ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4'
                  : 'space-y-2'
              }
            >
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className={viewMode === 'grid' ? 'h-44' : 'h-14'} />
              ))}
            </div>
          )}

          {!isLoadingFiltered && filteredTasks?.length === 0 && (
            <div className="text-center py-16">
              <Inbox className="mx-auto h-12 w-12 text-muted-foreground/50 mb-4" />
              <h3 className="text-lg font-medium mb-1">Задач не найдено</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Попробуйте изменить фильтры{canCreateTask(user) ? ' или создайте новую задачу' : ''}
              </p>
              {canCreateTask(user) && (
                <Button onClick={() => setDialogOpen(true)}>
                  <Plus className="mr-1 h-4 w-4" />
                  Создать задачу
                </Button>
              )}
            </div>
          )}

          {!isLoadingFiltered && filteredTasks && filteredTasks.length > 0 && (
            viewMode === 'grid' ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredTasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </div>
            ) : (
              <div className="space-y-1">
                {filteredTasks.map((task) => (
                  <TaskCard key={task.id} task={task} compact />
                ))}
              </div>
            )
          )}
        </>
      )}

      <TaskFormDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
