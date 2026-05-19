import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import ForceGraph2D from 'react-force-graph-2d';
import { Maximize2, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { STATUS_LABELS, PRIORITY_LABELS } from '@/lib/statusUtils';
import type { Task, TaskType, Status } from '@/types';

interface GraphNode {
  id: string;
  task: Task;
  level: number;
  hasChildren: boolean;
  isExpanded: boolean;
  // mutable layout state added by d3-force
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

interface GraphLink {
  source: string;
  target: string;
}

const TYPE_COLOR: Record<TaskType, string> = {
  GOAL: '#8B5CF6',     // violet
  EPIC: '#3B82F6',     // blue
  TASK: '#06B6D4',     // cyan
  SUBTASK: '#64748B',  // slate
};

const STATUS_RING: Record<Status, string> = {
  NEW: '#A78BFA',
  IN_PROGRESS: '#3B82F6',
  REVIEW: '#06B6D4',
  DONE: '#10B981',
  OVERDUE: '#EF4444',
};

const TYPE_SIZE: Record<TaskType, number> = {
  GOAL: 14,
  EPIC: 10,
  TASK: 7,
  SUBTASK: 5,
};

const TYPE_LABEL: Record<TaskType, string> = {
  GOAL: 'Цель',
  EPIC: 'Эпик',
  TASK: 'Задача',
  SUBTASK: 'Подзадача',
};

export function TaskGraphView({ tasks }: { tasks: Task[] }) {
  const navigate = useNavigate();
  const fgRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dims, setDims] = useState({ w: 800, h: 600 });
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    // Default: expand all GOAL roots so user sees the top of the org tree
    return new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id));
  });
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // Track container size for responsive sizing
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setDims({ w: el.clientWidth, h: Math.max(500, el.clientHeight) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Refresh expanded set when tasks change (e.g., on initial load)
  useEffect(() => {
    if (expanded.size === 0 && tasks.length > 0) {
      setExpanded(new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks]);

  // Build the visible graph based on expanded state
  const graphData = useMemo(() => {
    const taskById = new Map(tasks.map((t) => [t.id, t]));
    const childrenOf = new Map<string, Task[]>();
    tasks.forEach((t) => {
      if (t.parent_id) {
        if (!childrenOf.has(t.parent_id)) childrenOf.set(t.parent_id, []);
        childrenOf.get(t.parent_id)!.push(t);
      }
    });

    // Visible set: roots + descendants under expanded ancestors
    const visible = new Set<string>();
    const stack: { id: string; level: number }[] = [];
    tasks
      .filter((t) => !t.parent_id || !taskById.has(t.parent_id))
      .forEach((root) => stack.push({ id: root.id, level: 0 }));
    const levelOf = new Map<string, number>();
    while (stack.length > 0) {
      const { id, level } = stack.pop()!;
      if (visible.has(id)) continue;
      visible.add(id);
      levelOf.set(id, level);
      if (expanded.has(id)) {
        (childrenOf.get(id) ?? []).forEach((c) =>
          stack.push({ id: c.id, level: level + 1 })
        );
      }
    }

    const nodes: GraphNode[] = Array.from(visible).map((id) => {
      const task = taskById.get(id)!;
      return {
        id,
        task,
        level: levelOf.get(id) ?? 0,
        hasChildren: (childrenOf.get(id) ?? []).length > 0,
        isExpanded: expanded.has(id),
      };
    });

    const links: GraphLink[] = [];
    nodes.forEach((n) => {
      const pid = n.task.parent_id;
      if (pid && visible.has(pid)) {
        links.push({ source: pid, target: n.id });
      }
    });

    return { nodes, links };
  }, [tasks, expanded]);

  const toggleExpand = useCallback((nodeId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const expandAll = () => {
    setExpanded(new Set(tasks.filter((t) => (t.children_count ?? 0) > 0 || tasks.some((other) => other.parent_id === t.id)).map((t) => t.id)));
  };

  const collapseAll = () => {
    setExpanded(new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id)));
  };

  const fitView = () => {
    fgRef.current?.zoomToFit(400, 80);
  };

  // Custom node renderer: filled circle with type color + status ring + label
  const drawNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const n = node as GraphNode;
      const task = n.task;
      const size = TYPE_SIZE[task.type];
      const color = TYPE_COLOR[task.type];
      const ringColor = STATUS_RING[task.status];
      const isHovered = hoveredId === n.id;

      // Outer status ring
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size + 2, 0, 2 * Math.PI);
      ctx.fillStyle = ringColor;
      ctx.globalAlpha = isHovered ? 1 : 0.6;
      ctx.fill();
      ctx.globalAlpha = 1;

      // Inner type-colored circle
      ctx.beginPath();
      ctx.arc(node.x!, node.y!, size, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Expand indicator: small "+" badge if has children and not expanded
      if (n.hasChildren && !n.isExpanded) {
        ctx.fillStyle = '#FFFFFF';
        ctx.font = `bold ${size * 0.9}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('+', node.x!, node.y!);
      } else if (n.isExpanded && n.hasChildren) {
        // small "−" only on slightly larger nodes
        ctx.fillStyle = '#FFFFFF';
        ctx.font = `bold ${size * 0.9}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('−', node.x!, node.y!);
      }

      // Label — only for GOAL+EPIC, or on hover
      const showLabel =
        task.type === 'GOAL' ||
        task.type === 'EPIC' ||
        isHovered ||
        globalScale > 2.5;
      if (showLabel) {
        const fontSize = Math.max(10, 12 / Math.sqrt(globalScale));
        ctx.font = `${task.type === 'GOAL' ? 'bold ' : ''}${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const label = truncate(task.title, task.type === 'GOAL' ? 40 : 28);
        // Background pill for readability
        const w = ctx.measureText(label).width;
        ctx.fillStyle = 'rgba(15, 20, 36, 0.85)';
        ctx.fillRect(
          node.x! - w / 2 - 4,
          node.y! + size + 4,
          w + 8,
          fontSize + 4
        );
        ctx.fillStyle = '#E5E7EB';
        ctx.fillText(label, node.x!, node.y! + size + 6);
      }
    },
    [hoveredId]
  );

  // Link styling: subtle, slightly emphasized on hover of either end
  const linkColor = useCallback(
    (link: any) => {
      const sourceId = typeof link.source === 'string' ? link.source : link.source.id;
      const targetId = typeof link.target === 'string' ? link.target : link.target.id;
      if (hoveredId === sourceId || hoveredId === targetId) {
        return 'rgba(148, 163, 184, 0.9)';
      }
      return 'rgba(100, 116, 139, 0.35)';
    },
    [hoveredId]
  );

  const hoveredTask = hoveredId
    ? graphData.nodes.find((n) => n.id === hoveredId)?.task
    : null;

  return (
    <div
      ref={containerRef}
      className="relative w-full rounded-lg border bg-card/40 overflow-hidden"
      style={{ height: 'min(75vh, 800px)' }}
    >
      {/* Toolbar */}
      <div className="absolute top-3 left-3 z-10 flex gap-2 flex-wrap">
        <Button size="sm" variant="secondary" onClick={expandAll}>
          Раскрыть всё
        </Button>
        <Button size="sm" variant="outline" onClick={collapseAll}>
          <RotateCcw className="mr-1 h-3 w-3" />
          Свернуть
        </Button>
        <Button size="sm" variant="outline" onClick={fitView}>
          <Maximize2 className="mr-1 h-3 w-3" />
          Уместить
        </Button>
      </div>

      {/* Legend */}
      <div className="absolute top-3 right-3 z-10 rounded-md border bg-background/90 backdrop-blur px-3 py-2 text-[11px] space-y-1.5 max-w-[220px]">
        <div className="font-semibold text-foreground">Тип</div>
        <LegendDot color={TYPE_COLOR.GOAL} label="Цель" size={14} />
        <LegendDot color={TYPE_COLOR.EPIC} label="Эпик" size={10} />
        <LegendDot color={TYPE_COLOR.TASK} label="Задача" size={7} />
        <LegendDot color={TYPE_COLOR.SUBTASK} label="Подзадача" size={5} />
        <div className="font-semibold text-foreground pt-1.5 border-t">
          Статус (кольцо)
        </div>
        <LegendDot ring color={STATUS_RING.IN_PROGRESS} label="В работе" />
        <LegendDot ring color={STATUS_RING.OVERDUE} label="Просрочена" />
        <LegendDot ring color={STATUS_RING.DONE} label="Выполнена" />
      </div>

      {/* Tooltip for hovered task */}
      {hoveredTask && (
        <div className="absolute bottom-3 left-3 z-10 rounded-md border bg-background/95 backdrop-blur px-3 py-2 max-w-md shadow-lg pointer-events-none">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <Badge variant="outline" className="text-[10px]">
              {TYPE_LABEL[hoveredTask.type]}
            </Badge>
            <Badge
              className="text-[10px] border-0 text-white"
              style={{ backgroundColor: STATUS_RING[hoveredTask.status] }}
            >
              {STATUS_LABELS[hoveredTask.status]}
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              {PRIORITY_LABELS[hoveredTask.priority]} приоритет
            </span>
          </div>
          <div className="text-sm font-medium">{hoveredTask.title}</div>
          <div className="text-xs text-muted-foreground mt-1">
            {hoveredTask.assignee_name && (
              <span>👤 {hoveredTask.assignee_name}</span>
            )}
            {hoveredTask.assigned_department_name && (
              <span className="ml-3">📁 {hoveredTask.assigned_department_name}</span>
            )}
            <span className="ml-3">▰ {hoveredTask.progress}%</span>
          </div>
          <div className="text-[10px] text-muted-foreground mt-1.5">
            Клик — раскрыть/свернуть · Двойной клик — открыть карточку
          </div>
        </div>
      )}

      {/* The graph */}
      <ForceGraph2D
        ref={fgRef}
        width={dims.w}
        height={dims.h}
        graphData={graphData}
        nodeId="id"
        nodeRelSize={1}
        nodeCanvasObject={drawNode}
        nodePointerAreaPaint={(node: any, color, ctx) => {
          const n = node as GraphNode;
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(node.x!, node.y!, TYPE_SIZE[n.task.type] + 4, 0, 2 * Math.PI);
          ctx.fill();
        }}
        linkColor={linkColor}
        linkWidth={1.2}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleWidth={2}
        onNodeClick={(node: any) => {
          const n = node as GraphNode;
          if (n.hasChildren) toggleExpand(n.id);
        }}
        onNodeRightClick={(node: any) => {
          navigate(`/tasks/${(node as GraphNode).id}`);
        }}
        onNodeHover={(node: any) => setHoveredId(node?.id ?? null)}
        cooldownTicks={120}
        d3VelocityDecay={0.3}
        backgroundColor="transparent"
        enableNodeDrag={true}
      />

      {/* Hint at bottom right */}
      <div className="absolute bottom-3 right-3 z-10 text-[10px] text-muted-foreground bg-background/80 backdrop-blur rounded px-2 py-1 pointer-events-none">
        Колесо — масштаб · Перетаскивание — двигать
      </div>
    </div>
  );
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1).trim() + '…';
}

function LegendDot({
  color,
  label,
  size = 8,
  ring = false,
}: {
  color: string;
  label: string;
  size?: number;
  ring?: boolean;
}) {
  return (
    <div className="flex items-center gap-2">
      <span
        className="inline-block rounded-full shrink-0"
        style={{
          width: Math.max(8, size + 2),
          height: Math.max(8, size + 2),
          backgroundColor: ring ? 'transparent' : color,
          border: ring ? `2px solid ${color}` : 'none',
        }}
      />
      <span className="text-muted-foreground">{label}</span>
    </div>
  );
}
