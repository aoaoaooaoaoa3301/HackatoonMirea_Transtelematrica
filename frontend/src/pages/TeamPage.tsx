import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ChevronRight,
  ChevronDown,
  Users,
  User as UserIcon,
  AlertTriangle,
  Clock,
  Briefcase,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { TaskCard } from '@/components/tasks/TaskCard';
import { getDepartments } from '@/api/departments';
import { getUsers, getUserWorkload } from '@/api/users';
import { getTasks } from '@/api/tasks';
import {
  ROLE_LABELS,
  getCapacityColor,
  getCapacityBgColor,
} from '@/lib/statusUtils';
import type { User, Department } from '@/types';

function UserRow({ user, onClick }: { user: User; onClick: () => void }) {
  const { data: workload } = useQuery({
    queryKey: ['workload', user.id],
    queryFn: () => getUserWorkload(user.id),
    staleTime: 60_000,
  });

  const initials = user.full_name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2);

  return (
    <button
      onClick={onClick}
      className="flex items-center gap-3 w-full rounded-md p-3 hover:bg-accent/50 transition-colors text-left"
    >
      <Avatar className="h-9 w-9 shrink-0">
        <AvatarFallback className="text-xs bg-primary/10">{initials}</AvatarFallback>
      </Avatar>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{user.full_name}</p>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {ROLE_LABELS[user.role]}
          </Badge>
          {user.seniority && (
            <span className="text-[11px] text-muted-foreground">{user.seniority}</span>
          )}
        </div>
      </div>
      <div className="flex items-center gap-4 shrink-0">
        {workload ? (
          <>
            <div className="w-32 hidden sm:block">
              <div className="flex items-center gap-2">
                <Progress
                  value={Math.min(workload.capacity_util, 150)}
                  max={150}
                  className="h-2 flex-1"
                  indicatorClassName={getCapacityBgColor(workload.capacity_util)}
                />
                <span className={`text-xs font-medium w-10 text-right ${getCapacityColor(workload.capacity_util)}`}>
                  {Math.round(workload.capacity_util)}%
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground hidden md:flex">
              <span className="flex items-center gap-1">
                <Briefcase className="h-3 w-3" />
                {workload.open_tasks}
              </span>
              {workload.overdue_count > 0 && (
                <span className="flex items-center gap-1 text-rose-500">
                  <Clock className="h-3 w-3" />
                  {workload.overdue_count}
                </span>
              )}
              {workload.at_risk_count > 0 && (
                <span className="flex items-center gap-1 text-amber-500">
                  <AlertTriangle className="h-3 w-3" />
                  {workload.at_risk_count}
                </span>
              )}
            </div>
          </>
        ) : (
          <Skeleton className="h-4 w-32" />
        )}
      </div>
    </button>
  );
}

function DepartmentSection({
  dept,
  users,
  onUserClick,
}: {
  dept: Department;
  users: User[];
  onUserClick: (user: User) => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const deptUsers = users.filter((u) => u.department_id === dept.id);

  return (
    <Card>
      <CardHeader className="pb-2">
        <button
          className="flex items-center gap-2 w-full text-left"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <Users className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base flex-1">{dept.name}</CardTitle>
          <Badge variant="secondary">{deptUsers.length}</Badge>
        </button>
      </CardHeader>
      {expanded && (
        <CardContent className="pt-0">
          {deptUsers.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              Нет сотрудников
            </p>
          ) : (
            <div className="divide-y">
              {deptUsers.map((user) => (
                <UserRow key={user.id} user={user} onClick={() => onUserClick(user)} />
              ))}
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}

export default function TeamPage() {
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  // Deep-link from the dashboard workload list: /team?user=<id> opens that
  // employee's panel automatically once the users list is loaded.
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: departments, isLoading: deptLoading } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
  });

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => getUsers(),
  });

  useEffect(() => {
    const userId = searchParams.get('user');
    if (userId && users && !selectedUser) {
      const match = users.find((u) => u.id === userId);
      if (match) {
        setSelectedUser(match);
        // clear the param so closing the sheet doesn't re-open it
        searchParams.delete('user');
        setSearchParams(searchParams, { replace: true });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [users, searchParams]);

  const { data: userTasks } = useQuery({
    queryKey: ['tasks', 'user', selectedUser?.id],
    queryFn: () => getTasks({ assignee_id: selectedUser!.id }),
    enabled: !!selectedUser,
  });

  const { data: selectedWorkload } = useQuery({
    queryKey: ['workload', selectedUser?.id],
    queryFn: () => getUserWorkload(selectedUser!.id),
    enabled: !!selectedUser,
  });

  const isLoading = deptLoading || usersLoading;

  return (
    <div className="space-y-4">
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full" />
          ))}
        </div>
      ) : (
        <>
          {departments?.map((dept) => (
            <DepartmentSection
              key={dept.id}
              dept={dept}
              users={users ?? []}
              onUserClick={setSelectedUser}
            />
          ))}
          {/* Users without department */}
          {users?.filter((u) => !u.department_id).length ? (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <UserIcon className="h-4 w-4 text-muted-foreground" />
                  Без отдела
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="divide-y">
                  {users
                    ?.filter((u) => !u.department_id)
                    .map((user) => (
                      <UserRow key={user.id} user={user} onClick={() => setSelectedUser(user)} />
                    ))}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </>
      )}

      {/* User detail sheet */}
      <Sheet open={!!selectedUser} onOpenChange={(open) => !open && setSelectedUser(null)}>
        <SheetContent>
          {selectedUser && (
            <>
              <SheetHeader>
                <SheetTitle>{selectedUser.full_name}</SheetTitle>
                <SheetDescription>
                  {selectedUser.email} / {ROLE_LABELS[selectedUser.role]}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-4">
                {selectedWorkload && (
                  <div className="grid grid-cols-2 gap-3">
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold">{selectedWorkload.open_tasks}</p>
                      <p className="text-xs text-muted-foreground">Открытые</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <p className={`text-2xl font-bold ${getCapacityColor(selectedWorkload.capacity_util)}`}>
                        {Math.round(selectedWorkload.capacity_util)}%
                      </p>
                      <p className="text-xs text-muted-foreground">Загрузка</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold text-rose-500">{selectedWorkload.overdue_count}</p>
                      <p className="text-xs text-muted-foreground">Просрочено</p>
                    </div>
                    <div className="rounded-lg border p-3 text-center">
                      <p className="text-2xl font-bold text-amber-500">{selectedWorkload.at_risk_count}</p>
                      <p className="text-xs text-muted-foreground">В зоне риска</p>
                    </div>
                  </div>
                )}

                {selectedUser.skills.length > 0 && (
                  <div>
                    <p className="text-sm font-medium mb-2">Навыки</p>
                    <div className="flex flex-wrap gap-1">
                      {selectedUser.skills.map((skill) => (
                        <Badge key={skill} variant="secondary" className="text-xs">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <p className="text-sm font-medium mb-2">Задачи ({userTasks?.length ?? 0})</p>
                  <div className="space-y-1 max-h-[400px] overflow-y-auto">
                    {userTasks?.map((task) => (
                      <TaskCard key={task.id} task={task} compact />
                    ))}
                    {(!userTasks || userTasks.length === 0) && (
                      <p className="text-sm text-muted-foreground text-center py-4">
                        Нет назначенных задач
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}
