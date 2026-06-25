import { useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
} from '@xyflow/react';
import type { Connection, Edge, Node } from '@xyflow/react';
import { Handle, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useDevices } from '../context/NetworkContext';
import { Smartphone, Laptop, Tv, Monitor, Globe, Router } from 'lucide-react';

const DeviceNode = ({ data }: any) => {
  const isBlocked = data.isBlocked;
  let Icon = Smartphone;
  if (data.type === 'tv') Icon = Tv;
  else if (data.type === 'laptop') Icon = Laptop;
  else if (data.type === 'desktop') Icon = Monitor;
  else if (data.type === 'router') Icon = Router;
  else if (data.type === 'internet') Icon = Globe;

  const bgClass = data.type === 'internet' 
    ? 'bg-gradient-to-br from-blue-900 to-blue-950 border-blue-500 shadow-[0_0_15px_rgba(59,130,246,0.3)]' 
    : data.type === 'router'
    ? 'bg-gradient-to-br from-emerald-900 to-teal-950 border-emerald-500 shadow-[0_0_15px_rgba(16,185,129,0.3)]'
    : isBlocked 
    ? 'bg-gradient-to-br from-rose-900 to-red-950 border-red-500 shadow-[0_0_15px_rgba(239,68,68,0.3)]'
    : 'bg-gradient-to-br from-slate-800 to-slate-900 border-indigo-500 hover:shadow-[0_0_10px_rgba(99,102,241,0.3)]';

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  return (
    <div className={`px-4 py-3 rounded-xl border-2 flex flex-col items-center gap-2 min-w-[120px] transition-all duration-300 ${bgClass}`}>
      {data.type !== 'internet' && <Handle type="target" position={Position.Top} className="!w-2 !h-2 !bg-white !border-2 !border-gray-800" />}
      <div className={`p-2 rounded-lg bg-white/10 backdrop-blur-md`}>
        <Icon className={`w-6 h-6 ${isBlocked ? 'text-red-400' : 'text-blue-100'}`} />
      </div>
      <div className="text-center">
        <p className="text-sm font-bold text-white truncate max-w-[100px]">{data.label}</p>
        {data.ip && <p className="text-[10px] text-gray-400 font-mono mt-0.5">{data.ip}</p>}
        {data.bytes !== undefined && (
          <div className="mt-2 text-[11px] font-medium bg-black/40 px-2 py-0.5 rounded text-emerald-400 font-mono">
            ↓ {formatBytes(data.bytes)}
          </div>
        )}
      </div>
      {data.type !== 'device' && <Handle type="source" position={Position.Bottom} className="!w-2 !h-2 !bg-white !border-2 !border-gray-800" />}
    </div>
  );
};

const nodeTypes = {
  deviceNode: DeviceNode,
};

const initialNodes: Node[] = [
  {
    id: 'internet',
    position: { x: 400, y: 50 },
    data: { label: 'Internet (ISP)', type: 'internet' },
    type: 'deviceNode',
  },
  {
    id: 'router',
    position: { x: 400, y: 200 },
    data: { label: 'MikroTik Router', type: 'router', ip: '192.168.88.1' },
    type: 'deviceNode',
  },
];

const initialEdges: Edge[] = [
  { id: 'e-internet-router', source: 'internet', target: 'router', animated: true, style: { stroke: '#3B82F6', strokeWidth: 3 } },
];

export default function NetworkMap() {
  const { devices } = useDevices();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    // Generate nodes based on connected devices
    const deviceNodes: Node[] = devices.map((dev, index) => {
      // Calculate a nice radial or grid position around the router
      const x = 50 + (index % 4) * 150;
      const y = 300 + Math.floor(index / 4) * 100;
      
      const isBlocked = dev.is_blocked;
      
      const type = dev.hostname?.toLowerCase().includes('tv') ? 'tv' 
                 : dev.hostname?.toLowerCase().includes('mac') ? 'laptop'
                 : dev.hostname?.toLowerCase().includes('pc') ? 'desktop'
                 : 'device';

      return {
        id: dev.mac_address,
        position: { x, y },
        type: 'deviceNode',
        data: { 
          label: dev.hostname || 'Unknown', 
          ip: dev.ip_address,
          bytes: dev.bytes_total,
          isBlocked: isBlocked,
          type: type
        },
      };
    });

    const deviceEdges: Edge[] = devices.map((dev) => ({
      id: `e-router-${dev.mac_address}`,
      source: 'router',
      target: dev.mac_address,
      animated: !dev.is_blocked,
      style: { 
        stroke: dev.is_blocked ? '#EF4444' : '#6366F1',
        strokeWidth: 1.5,
        strokeDasharray: dev.is_blocked ? '5,5' : 'none'
      }
    }));

    setNodes([...initialNodes, ...deviceNodes]);
    setEdges([...initialEdges, ...deviceEdges]);
  }, [devices, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection | Edge) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <h2 className="text-xl font-bold text-fg-primary">Network Topology</h2>
        <p className="text-sm text-fg-muted mt-1">Real-time visual map of your connected devices.</p>
      </div>

      <div className="w-full h-[600px] border border-border-subtle rounded-xl overflow-hidden bg-bg-secondary">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
          colorMode="dark"
        >
          <Controls />
          <Background color="#334155" gap={16} />
        </ReactFlow>
      </div>
    </div>
  );
}
