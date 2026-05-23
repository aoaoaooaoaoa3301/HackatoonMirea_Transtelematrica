import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Shield, Plus, Pencil, Users } from 'lucide-react';
import { toast } from 'sonner';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

import { useAuth } from '@/hooks/useAuth';
import { canManageTeam } from '@/lib/permissions';
import { ROLE_LABELS } from '@/lib/statusUtils';
import { getUsers, createUser, updateUser } from '@/api/users';
import { getDepartments, createDepartment, updateDepartment } from '@/api/departments';
import type { User, Department, Role, UserCreatePayload, UserUpdatePayload } from '@/types';

/* ------------------------------------------------------------------ */
/*  User Dialog                                                        */
/* ------------------------------------------------------------------ */

interface UserDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editUser: User | null;
  departments: Department[];
}

function UserDialog({ open, onOpenChange, editUser, departments }: UserDialogProps) {
  const queryClient = useQueryClient();
  const isEdit = !!editUser;

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('EMPLOYEE');
  const [departmentId, setDepartmentId] = useState<string>('__none__');
  const [skills, setSkills] = useState('');
  const [seniority, setSeniority] = useState('');
  const [password, setPassword] = useState('');
  const [active, setActive] = useState(true);

  // Reset form when dialog opens
  const handleOpenChange = (v: boolean) => {
    if (v) {
      if (editUser) {
        setFullName(editUser.full_name);
        setEmail(editUser.email);
        setRole(editUser.role);
        setDepartmentId(editUser.department_id ?? '__none__');
        setSkills((editUser.skills ?? []).join(', '));
        setSeniority(editUser.seniority ?? '');
        setPassword('');
        setActive(editUser.active !== false);
      } else {
        setFullName('');
        setEmail('');
        setRole('EMPLOYEE');
        setDepartmentId('__none__');
        setSkills('');
        setSeniority('');
        setPassword('');
        setActive(true);
      }
    }
    onOpenChange(v);
  };

  const createMut = useMutation({
    mutationFn: (payload: UserCreatePayload) => createUser(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('Пользователь создан');
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Ошибка создания';
      toast.error(msg);
    },
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: UserUpdatePayload }) => updateUser(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      toast.success('Пользователь обновлён');
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Ошибка обновления';
      toast.error(msg);
    },
  });

  const isSaving = createMut.isPending || updateMut.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const parsedSkills = skills
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    const deptId = departmentId === '__none__' ? null : departmentId;

    if (isEdit) {
      const payload: UserUpdatePayload = {
        full_name: fullName,
        email,
        role,
        department_id: deptId,
        skills: parsedSkills,
        seniority: seniority || null,
        active,
      };
      if (password) payload.password = password;
      updateMut.mutate({ id: editUser.id, payload });
    } else {
      const payload: UserCreatePayload = {
        full_name: fullName,
        email,
        role,
        department_id: deptId,
        skills: parsedSkills,
        seniority: seniority || null,
        password: password || 'password',
      };
      createMut.mutate(payload);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Изменить пользователя' : 'Создать пользователя'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Измените данные сотрудника' : 'Заполните данные нового сотрудника'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="fullName">ФИО</Label>
            <Input id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label>Роль</Label>
            <Select value={role} onValueChange={(v) => setRole(v as Role)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="EMPLOYEE">{ROLE_LABELS.EMPLOYEE}</SelectItem>
                <SelectItem value="LEAD">{ROLE_LABELS.LEAD}</SelectItem>
                <SelectItem value="ADMIN">{ROLE_LABELS.ADMIN}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Отдел</Label>
            <Select value={departmentId} onValueChange={setDepartmentId}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Без отдела</SelectItem>
                {departments.map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {d.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="skills">Навыки (через запятую)</Label>
            <Input id="skills" value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="Python, React, SQL" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="seniority">Сениорити</Label>
            <Input id="seniority" value={seniority} onChange={(e) => setSeniority(e.target.value)} placeholder="Junior / Middle / Senior" />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Пароль</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isEdit ? 'Оставьте пустым, чтобы не менять' : 'По умолчанию: password'}
            />
          </div>
          {isEdit && (
            <div className="flex items-center gap-3">
              <Switch id="active" checked={active} onCheckedChange={setActive} />
              <Label htmlFor="active">Активен</Label>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Отмена
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Сохранение...' : isEdit ? 'Сохранить' : 'Создать'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/*  Department Dialog                                                  */
/* ------------------------------------------------------------------ */

interface DeptDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  editDept: Department | null;
  users: User[];
}

function DeptDialog({ open, onOpenChange, editDept, users }: DeptDialogProps) {
  const queryClient = useQueryClient();
  const isEdit = !!editDept;

  const [name, setName] = useState('');
  const [headUserId, setHeadUserId] = useState<string>('__none__');

  const handleOpenChange = (v: boolean) => {
    if (v) {
      if (editDept) {
        setName(editDept.name);
        setHeadUserId(editDept.head_user_id ?? '__none__');
      } else {
        setName('');
        setHeadUserId('__none__');
      }
    }
    onOpenChange(v);
  };

  const deptMembers = editDept ? users.filter((u) => u.department_id === editDept.id) : users;

  const createMut = useMutation({
    mutationFn: () => createDepartment({ name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      toast.success('Отдел создан');
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Ошибка создания';
      toast.error(msg);
    },
  });

  const updateMut = useMutation({
    mutationFn: () =>
      updateDepartment(editDept!.id, {
        name,
        head_user_id: headUserId === '__none__' ? null : headUserId,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['departments'] });
      toast.success('Отдел обновлён');
      onOpenChange(false);
    },
    onError: (err: unknown) => {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Ошибка обновления';
      toast.error(msg);
    },
  });

  const isSaving = createMut.isPending || updateMut.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isEdit) {
      updateMut.mutate();
    } else {
      createMut.mutate();
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Изменить отдел' : 'Создать отдел'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Измените название и руководителя отдела' : 'Введите название нового отдела'}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="deptName">Название</Label>
            <Input id="deptName" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          {isEdit && (
            <div className="space-y-2">
              <Label>Руководитель</Label>
              <Select value={headUserId} onValueChange={setHeadUserId}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Не назначен</SelectItem>
                  {deptMembers.map((u) => (
                    <SelectItem key={u.id} value={u.id}>
                      {u.full_name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Отмена
            </Button>
            <Button type="submit" disabled={isSaving}>
              {isSaving ? 'Сохранение...' : isEdit ? 'Сохранить' : 'Создать'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

/* ------------------------------------------------------------------ */
/*  Admin Page                                                         */
/* ------------------------------------------------------------------ */

export default function AdminPage() {
  const { user } = useAuth();

  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);

  const [deptDialogOpen, setDeptDialogOpen] = useState(false);
  const [editingDept, setEditingDept] = useState<Department | null>(null);

  const { data: users = [] } = useQuery({
    queryKey: ['users'],
    queryFn: () => getUsers(),
    enabled: canManageTeam(user),
  });

  const { data: departments = [] } = useQuery({
    queryKey: ['departments'],
    queryFn: getDepartments,
    enabled: canManageTeam(user),
  });

  if (!canManageTeam(user)) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Card className="max-w-sm w-full">
          <CardContent className="pt-6 text-center">
            <Shield className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <p className="text-lg font-medium">Недостаточно прав</p>
            <p className="text-sm text-muted-foreground mt-1">
              Эта страница доступна только администраторам
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  function openCreateUser() {
    setEditingUser(null);
    setUserDialogOpen(true);
  }

  function openEditUser(u: User) {
    setEditingUser(u);
    setUserDialogOpen(true);
  }

  function openCreateDept() {
    setEditingDept(null);
    setDeptDialogOpen(true);
  }

  function openEditDept(d: Department) {
    setEditingDept(d);
    setDeptDialogOpen(true);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Shield className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold tracking-tight">Администрирование</h1>
      </div>

      <Tabs defaultValue="users" className="space-y-4">
        <TabsList>
          <TabsTrigger value="users">Пользователи</TabsTrigger>
          <TabsTrigger value="departments">Отделы</TabsTrigger>
        </TabsList>

        {/* ── Users Tab ── */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{users.length} пользователей</p>
            <Button size="sm" onClick={openCreateUser}>
              <Plus className="h-4 w-4 mr-1" />
              Создать пользователя
            </Button>
          </div>

          <Card>
            <CardContent className="p-0">
              {/* Desktop table header */}
              <div className="hidden sm:grid grid-cols-[minmax(180px,1.2fr)_minmax(240px,1fr)_140px_minmax(160px,0.7fr)_110px_44px] gap-4 items-center px-4 py-2 border-b text-xs font-medium text-muted-foreground">
                <span>ФИО</span>
                <span className="text-center">Email</span>
                <span className="text-center">Роль</span>
                <span className="text-center">Отдел</span>
                <span className="text-center">Статус</span>
                <span />
              </div>
              <div className="divide-y">
                {users.map((u) => (
                  <div
                    key={u.id}
                    className="grid grid-cols-1 sm:grid-cols-[minmax(180px,1.2fr)_minmax(240px,1fr)_140px_minmax(160px,0.7fr)_110px_44px] gap-2 sm:gap-4 items-center px-4 py-3 hover:bg-accent/30 transition-colors"
                  >
                    <span className="text-sm font-medium truncate">{u.full_name}</span>
                    <span className="text-sm text-muted-foreground truncate sm:text-center">{u.email}</span>
                    <div className="sm:flex sm:justify-center">
                      <Badge variant="secondary" className="w-fit text-xs">
                        {ROLE_LABELS[u.role]}
                      </Badge>
                    </div>
                    <span className="text-sm text-muted-foreground truncate sm:text-center">
                      {u.department_name ?? 'Без отдела'}
                    </span>
                    <div className="sm:flex sm:justify-center">
                      <Badge variant={u.active !== false ? 'default' : 'destructive'} className="w-fit text-xs">
                        {u.active !== false ? 'Активен' : 'Отключён'}
                      </Badge>
                    </div>
                    <div className="sm:flex sm:justify-center">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEditUser(u)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
                {users.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">Нет пользователей</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── Departments Tab ── */}
        <TabsContent value="departments" className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">{departments.length} отделов</p>
            <Button size="sm" onClick={openCreateDept}>
              <Plus className="h-4 w-4 mr-1" />
              Создать отдел
            </Button>
          </div>

          <div className="grid gap-3">
            {departments.map((dept) => {
              const memberCount = users.filter((u) => u.department_id === dept.id).length;
              return (
                <Card key={dept.id}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Users className="h-4 w-4 text-muted-foreground" />
                        {dept.name}
                        <Badge variant="secondary" className="ml-1">{memberCount}</Badge>
                      </CardTitle>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEditDept(dept)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <p className="text-sm text-muted-foreground">
                      {dept.head_user_name
                        ? `Руководитель: ${dept.head_user_name}`
                        : 'Руководитель не назначен'}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
            {departments.length === 0 && (
              <p className="text-sm text-muted-foreground text-center py-8">Нет отделов</p>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* Dialogs */}
      <UserDialog
        open={userDialogOpen}
        onOpenChange={setUserDialogOpen}
        editUser={editingUser}
        departments={departments}
      />
      <DeptDialog
        open={deptDialogOpen}
        onOpenChange={setDeptDialogOpen}
        editDept={editingDept}
        users={users}
      />
    </div>
  );
}
