import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  ListTodo,
  KanbanSquare,
  Target,
  BarChart3,
  Users,
  Sparkles,
  MessageCircle,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Shield,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Separator } from '@/components/ui/separator';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { useAuth } from '@/hooks/useAuth';
import { ROLE_LABELS } from '@/lib/statusUtils';

const navItems = [
  { path: '/', label: 'Дашборд', icon: LayoutDashboard, adminOnly: false },
  { path: '/tasks', label: 'Задачи', icon: ListTodo, adminOnly: false },
  { path: '/kanban', label: 'Канбан', icon: KanbanSquare, adminOnly: false },
  { path: '/roadmap', label: 'Roadmap', icon: Target, adminOnly: false },
  { path: '/analytics', label: 'Аналитика', icon: BarChart3, adminOnly: false },
  { path: '/team', label: 'Команда', icon: Users, adminOnly: false },
  { path: '/ai', label: 'AI-помощник', icon: Sparkles, adminOnly: false },
  { path: '/telegram', label: 'Telegram', icon: MessageCircle, adminOnly: false },
  { path: '/admin', label: 'Администрирование', icon: Shield, adminOnly: true },
];

interface SidebarProps {
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

export function Sidebar({ mobileOpen, onMobileOpenChange }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { user, logout } = useAuth();

  const initials = user?.full_name
    ?.split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() ?? '?';

  const visibleNavItems = navItems.filter((item) => !item.adminOnly || user?.role === 'ADMIN');

  /** Shared navigation content used by both desktop sidebar and mobile drawer */
  function NavContent({ onNavigate }: { onNavigate?: () => void }) {
    return (
      <>
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {visibleNavItems.map((item) => {
            const isActive =
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onNavigate}
                className={cn(
                  'relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                )}
              >
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r bg-primary" />
                )}
                <item.icon className="h-5 w-5 shrink-0" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <Separator />

        {/* User section */}
        <div className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-secondary transition-colors"
              >
                <Avatar className="h-8 w-8 shrink-0">
                  <AvatarFallback className="text-xs bg-primary/10 text-primary">{initials}</AvatarFallback>
                </Avatar>
                {user && (
                  <div className="flex flex-col items-start overflow-hidden">
                    <span className="truncate text-sm font-medium">{user.full_name}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                      {ROLE_LABELS[user.role]}
                    </Badge>
                  </div>
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start">
              {user && (
                <div className="px-2 py-1.5">
                  <p className="text-sm font-medium">{user.full_name}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </div>
              )}
              <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
                <LogOut className="mr-2 h-4 w-4" />
                Выйти
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </>
    );
  }

  return (
    <>
      {/* ── Desktop sidebar (lg+) ── */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-40 hidden lg:flex h-screen flex-col border-r bg-card transition-all duration-300',
          collapsed ? 'w-16' : 'w-64'
        )}
      >
        {/* Header */}
        <div className="flex h-14 items-center gap-3 border-b px-4">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground font-semibold text-sm"
               style={{ fontFamily: "'Golos Text', system-ui, sans-serif" }}>
            T
          </div>
          {!collapsed && (
            <div className="flex flex-col overflow-hidden">
              <span className="text-sm font-semibold truncate" style={{ fontFamily: "'Golos Text', system-ui, sans-serif" }}>
                Транстелематика
              </span>
              <span className="text-[10px] text-muted-foreground">Управление задачами</span>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 overflow-y-auto p-2">
          {visibleNavItems.map((item) => {
            const isActive =
              item.path === '/'
                ? location.pathname === '/'
                : location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  'relative flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
                  collapsed && 'justify-center px-2'
                )}
                title={collapsed ? item.label : undefined}
              >
                {/* Active indicator bar */}
                {isActive && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r bg-primary" />
                )}
                <item.icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        <Separator />

        {/* User section */}
        <div className="p-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  'flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm hover:bg-secondary transition-colors',
                  collapsed && 'justify-center px-2'
                )}
              >
                <Avatar className="h-8 w-8 shrink-0">
                  <AvatarFallback className="text-xs bg-primary/10 text-primary">{initials}</AvatarFallback>
                </Avatar>
                {!collapsed && user && (
                  <div className="flex flex-col items-start overflow-hidden">
                    <span className="truncate text-sm font-medium">{user.full_name}</span>
                    <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                      {ROLE_LABELS[user.role]}
                    </Badge>
                  </div>
                )}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="top" align="start">
              {user && (
                <div className="px-2 py-1.5">
                  <p className="text-sm font-medium">{user.full_name}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </div>
              )}
              <DropdownMenuItem onClick={logout} className="text-destructive focus:text-destructive">
                <LogOut className="mr-2 h-4 w-4" />
                Выйти
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Collapse toggle */}
        <Button
          variant="ghost"
          size="icon"
          className="absolute -right-3 top-7 z-50 h-6 w-6 rounded-full border bg-background shadow-sm"
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <ChevronRight className="h-3 w-3" /> : <ChevronLeft className="h-3 w-3" />}
        </Button>
      </aside>

      {/* ── Mobile drawer (< lg) ── */}
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-72 p-0 flex flex-col">
          <SheetHeader className="px-4 py-3 border-b">
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground font-semibold text-sm"
                   style={{ fontFamily: "'Golos Text', system-ui, sans-serif" }}>
                T
              </div>
              <SheetTitle className="text-sm font-semibold" style={{ fontFamily: "'Golos Text', system-ui, sans-serif" }}>
                Транстелематика
              </SheetTitle>
            </div>
          </SheetHeader>
          <NavContent onNavigate={() => onMobileOpenChange(false)} />
        </SheetContent>
      </Sheet>
    </>
  );
}
