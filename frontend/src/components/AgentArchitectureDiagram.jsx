import { useCallback, useMemo } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import {
  User,
  FileText,
  Cpu,
  Wrench,
  Database,
  MessageSquare,
  Sparkles,
} from 'lucide-react';

// Custom Node Component
const CustomNode = ({ data }) => {
  return (
    <div
      className={`px-6 py-4 rounded-xl shadow-2xl border-2 transition-all hover:scale-105 hover:shadow-unicorn-500/50 backdrop-blur-sm ${data.className}`}
      style={{
        minWidth: data.large ? '240px' : '180px',
        minHeight: data.large ? '160px' : '120px',
      }}
    >
      <div className="flex flex-col items-center justify-center h-full space-y-2">
        <div
          className={`p-3 rounded-full bg-white/10 backdrop-blur-md ${
            data.large ? 'text-4xl' : 'text-2xl'
          }`}
        >
          {data.icon}
        </div>
        <div className="text-center">
          <h3
            className={`font-bold text-white ${
              data.large ? 'text-xl' : 'text-base'
            }`}
          >
            {data.label}
          </h3>
          {data.details && (
            <div className="mt-2 space-y-1">
              {data.details.map((detail, idx) => (
                <p
                  key={idx}
                  className="text-xs text-white/80 font-medium"
                >
                  {detail}
                </p>
              ))}
            </div>
          )}
        </div>
        {data.badge && (
          <span className="text-xs px-2 py-1 rounded-full bg-white/20 text-white font-medium">
            {data.badge}
          </span>
        )}
      </div>
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

const AgentArchitectureDiagram = ({ agent }) => {
  // Create nodes based on agent data
  const initialNodes = useMemo(() => {
    const tools = agent.agentTools || [];
    const toolsPreview = tools.length > 0
      ? tools.slice(0, 3).map(t => t.tool.name).join(', ')
      : 'None';
    const toolsBadge = tools.length > 3 ? `+${tools.length - 3} more` : null;

    return [
      {
        id: '1',
        type: 'custom',
        position: { x: 400, y: 50 },
        data: {
          label: 'User Input',
          icon: <User className="w-6 h-6" />,
          className: 'bg-gradient-to-br from-blue-500 to-cyan-500 border-blue-400',
        },
      },
      {
        id: '2',
        type: 'custom',
        position: { x: 400, y: 200 },
        data: {
          label: 'System Prompt',
          icon: <FileText className="w-6 h-6" />,
          details: [agent.systemPrompt?.substring(0, 40) + '...' || 'No prompt set'],
          className: 'bg-gradient-to-br from-purple-500 to-violet-500 border-purple-400',
        },
      },
      {
        id: '3',
        type: 'custom',
        position: { x: 360, y: 380 },
        data: {
          label: agent.model || 'Model',
          icon: <Sparkles className="w-8 h-8" />,
          details: [
            `Temperature: ${agent.temperature || 0.7}`,
            `Max Tokens: ${agent.maxTokens || 4096}`,
          ],
          large: true,
          className: 'bg-gradient-to-br from-pink-500 to-purple-600 border-pink-400',
        },
      },
      {
        id: '4',
        type: 'custom',
        position: { x: 150, y: 600 },
        data: {
          label: 'Tools',
          icon: <Wrench className="w-6 h-6" />,
          details: [toolsPreview],
          badge: toolsBadge,
          className: 'bg-gradient-to-br from-cyan-500 to-blue-500 border-cyan-400',
        },
      },
      {
        id: '5',
        type: 'custom',
        position: { x: 650, y: 600 },
        data: {
          label: 'Memory',
          icon: <Database className="w-6 h-6" />,
          details: ['Contextual', 'Session-based'],
          className: 'bg-gradient-to-br from-emerald-500 to-green-600 border-emerald-400',
        },
      },
      {
        id: '6',
        type: 'custom',
        position: { x: 400, y: 780 },
        data: {
          label: 'Response Output',
          icon: <MessageSquare className="w-6 h-6" />,
          className: 'bg-gradient-to-br from-emerald-500 to-teal-500 border-emerald-400',
        },
      },
    ];
  }, [agent]);

  const initialEdges = useMemo(
    () => [
      {
        id: 'e1-2',
        source: '1',
        target: '2',
        animated: true,
        style: { stroke: '#60a5fa', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#60a5fa',
        },
      },
      {
        id: 'e2-3',
        source: '2',
        target: '3',
        animated: true,
        style: { stroke: '#a78bfa', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#a78bfa',
        },
      },
      {
        id: 'e3-4',
        source: '3',
        target: '4',
        animated: true,
        style: { stroke: '#22d3ee', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#22d3ee',
        },
      },
      {
        id: 'e3-5',
        source: '3',
        target: '5',
        animated: true,
        style: { stroke: '#10b981', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#10b981',
        },
      },
      {
        id: 'e4-6',
        source: '4',
        target: '6',
        animated: true,
        style: { stroke: '#14b8a6', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#14b8a6',
        },
      },
      {
        id: 'e5-6',
        source: '5',
        target: '6',
        animated: true,
        style: { stroke: '#14b8a6', strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#14b8a6',
        },
      },
    ],
    []
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gradient mb-2">
            Agent Architecture
          </h2>
          <p className="text-slate-400">
            Visual representation of how {agent.displayName || agent.name} processes requests
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <span className="px-3 py-1 rounded-full bg-unicorn-500/20 text-unicorn-300 text-sm">
            Interactive Diagram
          </span>
        </div>
      </div>

      {/* React Flow Diagram */}
      <div
        className="rounded-xl border-2 border-slate-700 overflow-hidden"
        style={{ height: '700px' }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          className="bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900"
        >
          <Background
            color="#475569"
            gap={16}
            size={1}
            variant="dots"
          />
          <Controls
            className="bg-slate-800 border border-slate-700 rounded-lg"
            showInteractive={false}
          />
          <MiniMap
            className="bg-slate-800 border border-slate-700 rounded-lg"
            nodeColor={(node) => {
              if (node.data.className.includes('blue')) return '#3b82f6';
              if (node.data.className.includes('purple')) return '#a855f7';
              if (node.data.className.includes('pink')) return '#ec4899';
              if (node.data.className.includes('cyan')) return '#06b6d4';
              if (node.data.className.includes('emerald')) return '#10b981';
              return '#6366f1';
            }}
            maskColor="rgba(0, 0, 0, 0.7)"
          />
        </ReactFlow>
      </div>

      {/* Legend */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <div className="w-4 h-4 rounded-full bg-gradient-to-br from-blue-500 to-cyan-500"></div>
          <div>
            <p className="text-sm font-medium">User Input</p>
            <p className="text-xs text-slate-400">Initial request</p>
          </div>
        </div>
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <div className="w-4 h-4 rounded-full bg-gradient-to-br from-purple-500 to-violet-500"></div>
          <div>
            <p className="text-sm font-medium">System Prompt</p>
            <p className="text-xs text-slate-400">Agent instructions</p>
          </div>
        </div>
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <div className="w-4 h-4 rounded-full bg-gradient-to-br from-pink-500 to-purple-600"></div>
          <div>
            <p className="text-sm font-medium">Model</p>
            <p className="text-xs text-slate-400">AI processing core</p>
          </div>
        </div>
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <div className="w-4 h-4 rounded-full bg-gradient-to-br from-cyan-500 to-blue-500"></div>
          <div>
            <p className="text-sm font-medium">Tools</p>
            <p className="text-xs text-slate-400">External capabilities</p>
          </div>
        </div>
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <div className="w-4 h-4 rounded-full bg-gradient-to-br from-emerald-500 to-green-600"></div>
          <div>
            <p className="text-sm font-medium">Memory</p>
            <p className="text-xs text-slate-400">Context storage</p>
          </div>
        </div>
        <div className="flex items-center space-x-3 p-3 rounded-lg bg-slate-800/50 border border-slate-700">
          <div className="w-4 h-4 rounded-full bg-gradient-to-br from-emerald-500 to-teal-500"></div>
          <div>
            <p className="text-sm font-medium">Response</p>
            <p className="text-xs text-slate-400">Final output</p>
          </div>
        </div>
      </div>

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h3 className="font-semibold mb-2 flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-unicorn-400" />
            <span>Processing Pipeline</span>
          </h3>
          <p className="text-sm text-slate-400">
            Each request flows from user input through the system prompt to the model,
            which leverages tools and memory to generate contextual responses.
          </p>
        </div>
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h3 className="font-semibold mb-2 flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-unicorn-400" />
            <span>Interactive Features</span>
          </h3>
          <p className="text-sm text-slate-400">
            Zoom, pan, and drag nodes to explore the architecture. Use the minimap
            for navigation and controls for precise viewing.
          </p>
        </div>
      </div>
    </div>
  );
};

export default AgentArchitectureDiagram;
