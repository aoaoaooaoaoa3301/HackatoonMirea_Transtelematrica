import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Plus, Search, Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TaskFormDialog } from '@/components/tasks/TaskFormDialog';

const pageTitles: Record<string, string> = {
  '/': 'Дашборд',
  '/tasks': 'Задачи',
  '/kanban': 'Канбан-доска',
  '/roadmap': 'Roadmap',
  '/analytics': 'Аналитика',
  '/team': 'Команда',
  '/ai': 'AI-помощник',
};

export function Topbar() {
  const location = useLocation();
  const [dark, setDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return document.documentElement.classList.contains('dark');
    }
    return false;
  });
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);

  const title =
    pageTitles[location.pathname] ??
    (location.pathname.startsWith('/tasks/') ? 'Детали задачи' : 'Страница');

  useEffect(() => {
    if (dark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [dark]);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
        <h1 className="text-lg font-semibold">{title}</h1>

        <div className="flex-1" />

        <div className="relative hidden md:block">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Поиск... (Cmd+K)"
            className="w-64 pl-8"
            onFocus={(e) => e.target.blur()}
          />
        </div>

        <Button size="sm" onClick={() => setTaskDialogOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          Создать
        </Button>

        <Button variant="ghost" size="icon" onClick={() => setDark(!dark)}>
          {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </header>

      <TaskFormDialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen} />
    </>
  );
}
