import { useEffect, useState } from 'react';
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const SystemMetrics = () => {
  const [data, setData] = useState([]);

  useEffect(() => {
    // Generate mock data
    const mockData = Array.from({ length: 10 }, (_, i) => ({
      time: `${i * 5}m`,
      cpu: Math.floor(Math.random() * 40) + 30,
      memory: Math.floor(Math.random() * 30) + 50,
      tasks: Math.floor(Math.random() * 20) + 10,
      agents: Math.floor(Math.random() * 5) + 15
    }));
    setData(mockData);
  }, []);

  return (
    <div className="card">
      <h2 className="text-xl font-semibold mb-4">System Performance</h2>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h3 className="text-sm text-slate-400 mb-3">Resource Usage</h3>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={data}>
              <defs>
                <linearGradient id="colorCpu" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#ec4899" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#ec4899" stopOpacity={0.1}/>
                </linearGradient>
                <linearGradient id="colorMemory" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.8}/>
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0.1}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid rgba(100, 116, 139, 0.3)',
                  borderRadius: '8px'
                }}
              />
              <Area type="monotone" dataKey="cpu" stroke="#ec4899" fillOpacity={1} fill="url(#colorCpu)" />
              <Area type="monotone" dataKey="memory" stroke="#06b6d4" fillOpacity={1} fill="url(#colorMemory)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div>
          <h3 className="text-sm text-slate-400 mb-3">Agent Activity</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
              <YAxis stroke="#64748b" fontSize={12} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'rgba(15, 23, 42, 0.9)',
                  border: '1px solid rgba(100, 116, 139, 0.3)',
                  borderRadius: '8px'
                }}
              />
              <Line type="monotone" dataKey="agents" stroke="#10b981" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="tasks" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default SystemMetrics;