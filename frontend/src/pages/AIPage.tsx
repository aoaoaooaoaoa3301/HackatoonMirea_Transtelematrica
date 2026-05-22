import { useState } from 'react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { AIChatPanel } from '@/components/ai/AIChatPanel';
import { useAuth } from '@/hooks/useAuth';

export default function AIPage() {
  const [companyScope, setCompanyScope] = useState(true);
  const { user } = useAuth();

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] sm:h-[calc(100vh-7rem)]">
      {/* Context toggle */}
      <div className="flex items-center justify-end gap-2 sm:gap-3 pb-3 border-b mb-0 flex-wrap">
        <Label htmlFor="scope-toggle" className="text-sm text-muted-foreground">
          Контекст:
        </Label>
        <div className="flex items-center gap-2">
          <span className={`text-sm ${!companyScope ? 'font-medium' : 'text-muted-foreground'}`}>
            Мой отдел
          </span>
          <Switch
            id="scope-toggle"
            checked={companyScope}
            onCheckedChange={setCompanyScope}
          />
          <span className={`text-sm ${companyScope ? 'font-medium' : 'text-muted-foreground'}`}>
            Вся компания
          </span>
        </div>
      </div>

      {/* Chat */}
      <div className="flex-1 overflow-hidden">
        <AIChatPanel
          contextScope={companyScope ? 'all' : 'department'}
          contextDeptId={user?.department_id ?? undefined}
        />
      </div>
    </div>
  );
}
