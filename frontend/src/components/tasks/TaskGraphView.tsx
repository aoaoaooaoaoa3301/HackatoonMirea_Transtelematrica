import { useMemo, useRef, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { hierarchy, tree, HierarchyPointNode } from 'd3-hierarchy';
import { Maximize2, RotateCcw, ZoomIn, ZoomOut } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { STATUS_LABELS, PRIORITY_LABELS } from '@/lib/statusUtils';
import type { Task, TaskType, Status } from '@/types';

interface TreeDatum {
  id: string;
  task: Task | null; // null for the synthetic root
  hasChildren: boolean;
  isExpanded: boolean;
  children: TreeDatum[];
}

type PointNode = HierarchyPointNode<TreeDatum>;

const TYPE_COLOR: Record<TaskType, string> = {
  GOAL: '#8B5CF6',
  EPIC: '#3B82F6',
  TASK: '#06B6D4',
  SUBTASK: '#64748B',
};

const STATUS_RING: Record<Status, string> = {
  NEW: '#A78BFA',
  IN_PROGRESS: '#3B82F6',
  REVIEW: '#06B6D4',
  DONE: '#10B981',
  OVERDUE: '#EF4444',
};

const TYPE_RADIUS: Record<TaskType, number> = {
  GOAL: 13,
  EPIC: 10,
  TASK: 7,
  SUBTASK: 5,
};

const TYPE_LABEL_RU: Record<TaskType, string> = {
  GOAL: 'Цель',
  EPIC: 'Эпик',
  TASK: 'Задача',
  SUBTASK: 'Подзадача',
};

// Horizontal node spacing (column per depth level) + vertical row spacing.
// Row height accommodates the 2-line label (title + assignee/dept/% subtitle)
// without overlap between siblings or between ancestors at neighbouring rows.
const COL_WIDTH = 290;
const ROW_HEIGHT = 56;

function buildHierarchy(tasks: Task[], expandedIds: Set<string>): TreeDatum {
  // Graph view is the "strategic shape" — show only GOALs and their descendants.
  // Operational/orphan tasks (no GOAL ancestor) live in the "По целям" and
  // "Список" tabs; surfacing them here only stretches the canvas and dilutes
  // the signal of "how decomposed is each goal".
  const childrenByParent = new Map<string, Task[]>();
  tasks.forEach((t) => {
    if (!t.parent_id) return;
    if (!childrenByParent.has(t.parent_id)) childrenByParent.set(t.parent_id, []);
    childrenByParent.get(t.parent_id)!.push(t);
  });

  const goals = tasks.filter((t) => t.type === 'GOAL');

  function walk(task: Task): TreeDatum {
    const kids = childrenByParent.get(task.id) ?? [];
    const isExpanded = expandedIds.has(task.id);
    return {
      id: task.id,
      task,
      hasChildren: kids.length > 0,
      isExpanded,
      children: isExpanded ? kids.map(walk) : [],
    };
  }

  return {
    id: '__root__',
    task: null,
    hasChildren: goals.length > 0,
    isExpanded: true,
    children: goals.map(walk),
  };
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1).trim() + '…';
}

function bezierPath(s: PointNode, t: PointNode): string {
  // Horizontal layout: x is vertical, y is horizontal (per d3.tree() convention)
  const sx = s.y;
  const sy = s.x;
  const tx = t.y;
  const ty = t.x;
  const midX = (sx + tx) / 2;
  return `M ${sx},${sy} C ${midX},${sy} ${midX},${ty} ${tx},${ty}`;
}

export function TaskGraphView({ tasks }: { tasks: Task[] }) {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [dims, setDims] = useState({ w: 1000, h: 600 });

  // Expanded set: default = expand all GOALs (so user sees first level of decomposition)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    return new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id));
  });
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // Pan + zoom state
  const [transform, setTransform] = useState({ x: 60, y: 0, k: 1 });
  const panStateRef = useRef<{ dragging: boolean; sx: number; sy: number; ox: number; oy: number }>({
    dragging: false, sx: 0, sy: 0, ox: 0, oy: 0,
  });

  // Re-initialize expanded when tasks change
  useEffect(() => {
    if (expandedIds.size === 0 && tasks.length > 0) {
      setExpandedIds(new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks]);

  // Resize observer
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      setDims({ w: el.clientWidth, h: Math.max(500, el.clientHeight) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Compute layout via d3 tree
  const { nodes, links, bounds } = useMemo(() => {
    const root = hierarchy<TreeDatum>(buildHierarchy(tasks, expandedIds));
    const layout = tree<TreeDatum>().nodeSize([ROW_HEIGHT, COL_WIDTH]);
    layout(root);

    const allNodes = root.descendants() as PointNode[];
    const visibleNodes = allNodes.filter((n) => n.data.id !== '__root__');
    const visibleLinks = (root.links() as { source: PointNode; target: PointNode }[]).filter(
      (l) => l.source.data.id !== '__root__'
    );

    // Compute bounds for fit-to-view
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    visibleNodes.forEach((n) => {
      // After horizontal layout: position is (y, x)
      minX = Math.min(minX, n.y);
      maxX = Math.max(maxX, n.y);
      minY = Math.min(minY, n.x);
      maxY = Math.max(maxY, n.x);
    });
    if (!isFinite(minX)) {
      minX = 0; maxX = 0; minY = 0; maxY = 0;
    }
    return {
      nodes: visibleNodes,
      links: visibleLinks,
      bounds: { minX, maxX, minY, maxY },
    };
  }, [tasks, expandedIds]);

  const toggleNode = useCallback((id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const expandAll = () => {
    const withChildren = new Set<string>();
    const childIds = new Set(tasks.filter((t) => t.parent_id).map((t) => t.parent_id!));
    tasks.forEach((t) => {
      if (childIds.has(t.id)) withChildren.add(t.id);
    });
    setExpandedIds(withChildren);
  };

  const collapseToGoals = () => {
    setExpandedIds(new Set(tasks.filter((t) => t.type === 'GOAL').map((t) => t.id)));
  };

  const fitToView = useCallback(() => {
    const { minX, maxX, minY, maxY } = bounds;
    const contentW = (maxX - minX) + 320; // padding for labels
    const contentH = (maxY - minY) + 80;
    const k = Math.min(dims.w / contentW, dims.h / contentH, 1.2);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    setTransform({
      x: dims.w / 2 - cx * k,
      y: dims.h / 2 - cy * k,
      k,
    });
  }, [bounds, dims]);

  // Auto-fit after layout changes (debounced via effect deps)
  useEffect(() => {
    if (nodes.length > 0) {
      // Only auto-fit on first render or major changes
      fitToView();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks]);

  // Pan handlers
  const onMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest('[data-node-id]')) return; // don't pan when clicking a node
    panStateRef.current = {
      dragging: true,
      sx: e.clientX,
      sy: e.clientY,
      ox: transform.x,
      oy: transform.y,
    };
  };
  const onMouseMove = (e: React.MouseEvent) => {
    if (!panStateRef.current.dragging) return;
    const dx = e.clientX - panStateRef.current.sx;
    const dy = e.clientY - panStateRef.current.sy;
    setTransform((t) => ({ ...t, x: panStateRef.current.ox + dx, y: panStateRef.current.oy + dy }));
  };
  const onMouseUp = () => {
    panStateRef.current.dragging = false;
  };

  // Wheel zoom
  const onWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = -e.deltaY * 0.001;
    const factor = Math.exp(delta);
    setTransform((t) => {
      const newK = Math.max(0.3, Math.min(2.5, t.k * factor));
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { ...t, k: newK };
      const px = e.clientX - rect.left;
      const py = e.clientY - rect.top;
      // Zoom around cursor: keep the point under cursor fixed in screen space
      const nx = px - (px - t.x) * (newK / t.k);
      const ny = py - (py - t.y) * (newK / t.k);
      return { x: nx, y: ny, k: newK };
    });
  };

  const zoomIn = () => setTransform((t) => ({ ...t, k: Math.min(2.5, t.k * 1.25) }));
  const zoomOut = () => setTransform((t) => ({ ...t, k: Math.max(0.3, t.k / 1.25) }));

  const hoveredTask = useMemo(() => {
    if (!hoveredId) return null;
    return tasks.find((t) => t.id === hoveredId) ?? null;
  }, [hoveredId, tasks]);

  return (
    <div
      ref={containerRef}
      className="relative w-full rounded-lg border bg-card/40 overflow-hidden select-none"
      style={{ height: 'min(78vh, 820px)' }}
    >
      {/* Toolbar */}
      <div className="absolute top-3 left-3 z-10 flex gap-2 flex-wrap">
        <Button size="sm" variant="secondary" onClick={expandAll}>
          Раскрыть всё
        </Button>
        <Button size="sm" variant="outline" onClick={collapseToGoals}>
          <RotateCcw className="mr-1 h-3 w-3" />
          Только цели
        </Button>
        <Button size="sm" variant="outline" onClick={fitToView}>
          <Maximize2 className="mr-1 h-3 w-3" />
          Уместить
        </Button>
        <div className="flex rounded-md border bg-background">
          <Button size="sm" variant="ghost" className="h-9 rounded-r-none" onClick={zoomOut}>
            <ZoomOut className="h-3 w-3" />
          </Button>
          <Button size="sm" variant="ghost" className="h-9 rounded-l-none" onClick={zoomIn}>
            <ZoomIn className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* Legend */}
      <div className="absolute top-3 right-3 z-10 rounded-md border bg-background/90 backdrop-blur px-3 py-2 text-[11px] space-y-1">
        <div className="font-semibold text-foreground mb-1">Тип узла</div>
        <LegendItem color={TYPE_COLOR.GOAL} label="Цель" size={13} />
        <LegendItem color={TYPE_COLOR.EPIC} label="Эпик" size={10} />
        <LegendItem color={TYPE_COLOR.TASK} label="Задача" size={7} />
        <LegendItem color={TYPE_COLOR.SUBTASK} label="Подзадача" size={5} />
        <div className="font-semibold text-foreground pt-1.5 mt-1.5 border-t mb-1">Кольцо</div>
        <LegendItem ring color={STATUS_RING.IN_PROGRESS} label="В работе" />
        <LegendItem ring color={STATUS_RING.OVERDUE} label="Просрочена" />
        <LegendItem ring color={STATUS_RING.DONE} label="Выполнена" />
      </div>

      {/* Tooltip on hover */}
      {hoveredTask && (
        <div className="absolute bottom-3 left-3 z-10 rounded-md border bg-background/95 backdrop-blur px-3 py-2 max-w-md shadow-lg pointer-events-none">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <Badge variant="outline" className="text-[10px]">
              {TYPE_LABEL_RU[hoveredTask.type]}
            </Badge>
            <Badge
              className="text-[10px] border-0 text-white"
              style={{ backgroundColor: STATUS_RING[hoveredTask.status] }}
            >
              {STATUS_LABELS[hoveredTask.status]}
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              {PRIORITY_LABELS[hoveredTask.priority]}
            </span>
          </div>
          <div className="text-sm font-medium">{hoveredTask.title}</div>
          <div className="text-xs text-muted-foreground mt-1 flex gap-3 flex-wrap">
            {hoveredTask.assignee_name && <span>👤 {hoveredTask.assignee_name}</span>}
            {hoveredTask.assigned_department_name && (
              <span>📁 {hoveredTask.assigned_department_name}</span>
            )}
            <span>▰ {hoveredTask.progress}%</span>
          </div>
          <div className="text-[10px] text-muted-foreground mt-1.5">
            Клик — раскрыть/свернуть · Правый клик — открыть карточку
          </div>
        </div>
      )}

      <div className="absolute bottom-3 right-3 z-10 text-[10px] text-muted-foreground bg-background/80 backdrop-blur rounded px-2 py-1 pointer-events-none">
        Колесо — масштаб · Перетаскивание холста — двигать
      </div>

      {/* SVG canvas */}
      <svg
        ref={svgRef}
        width={dims.w}
        height={dims.h}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
        onWheel={onWheel}
        style={{
          cursor: panStateRef.current.dragging ? 'grabbing' : 'grab',
          display: 'block',
        }}
      >
        <g
          style={{
            transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`,
            transformOrigin: '0 0',
            transition: panStateRef.current.dragging ? 'none' : 'transform 350ms cubic-bezier(.2,.7,.3,1)',
          }}
        >
          {/* Links */}
          <g style={{ pointerEvents: 'none' }}>
            {links.map((link, i) => {
              const isHovered =
                hoveredId === link.source.data.id || hoveredId === link.target.data.id;
              return (
                <path
                  key={`l-${link.source.data.id}-${link.target.data.id}-${i}`}
                  d={bezierPath(link.source, link.target)}
                  fill="none"
                  stroke={isHovered ? 'rgba(148,163,184,0.95)' : 'rgba(100,116,139,0.45)'}
                  strokeWidth={isHovered ? 1.8 : 1.2}
                  style={{ transition: 'all 300ms ease' }}
                />
              );
            })}
          </g>

          {/* Nodes */}
          <g>
            {nodes.map((n) => {
              const task = n.data.task!;
              const r = TYPE_RADIUS[task.type];
              const fill = TYPE_COLOR[task.type];
              const ring = STATUS_RING[task.status];
              const isHovered = hoveredId === task.id;
              return (
                <g
                  key={task.id}
                  data-node-id={task.id}
                  transform={`translate(${n.y},${n.x})`}
                  style={{ transition: 'transform 350ms cubic-bezier(.2,.7,.3,1)', cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredId(task.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (n.data.hasChildren) toggleNode(task.id);
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    navigate(`/tasks/${task.id}`);
                  }}
                >
                  {/* Status ring */}
                  <circle r={r + 2.5} fill={ring} opacity={isHovered ? 1 : 0.55} />
                  {/* Type-coloured body */}
                  <circle r={r} fill={fill} />
                  {/* Toggle indicator */}
                  {n.data.hasChildren && (
                    <text
                      x={0}
                      y={0}
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize={r * 1.1}
                      fontWeight={700}
                      fill="#FFFFFF"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {n.data.isExpanded ? '−' : '+'}
                    </text>
                  )}
                  {/* Label to the right of the node */}
                  <text
                    x={r + 8}
                    y={0}
                    dominantBaseline="central"
                    fontSize={task.type === 'GOAL' ? 14 : task.type === 'EPIC' ? 12.5 : 11.5}
                    fontWeight={task.type === 'GOAL' ? 700 : task.type === 'EPIC' ? 600 : 500}
                    fill={isHovered ? '#FFFFFF' : task.type === 'GOAL' ? '#F8FAFC' : '#E5E7EB'}
                    style={{ pointerEvents: 'none', userSelect: 'none' }}
                  >
                    {truncate(task.title, 38)}
                  </text>
                  {/* Sub-label: assignee + progress, only on hover or for GOAL/EPIC */}
                  {(task.type === 'GOAL' || task.type === 'EPIC' || isHovered) && (
                    <text
                      x={r + 8}
                      y={15}
                      dominantBaseline="central"
                      fontSize={10}
                      fill="#CBD5E1"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {task.assignee_name ?? '—'}
                      {task.assigned_department_name ? ` · ${task.assigned_department_name}` : ''}
                      {` · ${task.progress}%`}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      {/* Empty state */}
      {nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-center">
          <div>
            <p className="text-sm text-muted-foreground">
              Нет задач для отображения. Создайте первую стратегическую цель.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function LegendItem({
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
