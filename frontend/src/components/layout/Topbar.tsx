import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, Plus, Search, Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { TaskFormDialog } from '@/components/tasks/TaskFormDialog';
import { useTheme } from '@/hooks/useTheme';
import { useAuthStore } from '@/store/authStore';
import { canCreateTask } from '@/lib/permissions';

const pageTitles: Record<string, string> = {
  '/': 'Дашборд',
  '/tasks': 'Задачи',
  '/kanban': 'Канбан-доска',
  '/roadmap': 'Roadmap',
  '/analytics': 'Аналитика',
  '/team': 'Команда',
  '/ai': 'AI-помощник',
  '/telegram': 'Telegram-бот',
  '/admin': 'Администрирование',
};

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const location = useLocation();
  const { theme, toggle } = useTheme();
  const user = useAuthStore((s) => s.user);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);

  const title =
    pageTitles[location.pathname] ??
    (location.pathname.startsWith('/tasks/') ? 'Детали задачи' : 'Страница');

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center gap-4 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-4 sm:px-6">
        {/* Hamburger -- visible only below lg */}
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden shrink-0"
          onClick={onMenuClick}
          aria-label="Открыть меню"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <h1 className="text-lg font-semibold truncate">{title}</h1>

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

        {canCreateTask(user) && (
          <Button size="sm" onClick={() => setTaskDialogOpen(true)}>
            <Plus className="h-4 w-4 sm:mr-1" />
            <span className="hidden sm:inline">Создать</span>
          </Button>
        )}

        <Button variant="ghost" size="icon" onClick={toggle}>
          {theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
        </Button>
      </header>

      <TaskFormDialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen} />
    </>
  );
}
