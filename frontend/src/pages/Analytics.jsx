import { BarChart3 } from 'lucide-react';

const Analytics = () => {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-gradient mb-6">Analytics</h1>
      <div className="card">
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <BarChart3 className="w-16 h-16 text-cyan-400 mx-auto mb-4" />
            <h2 className="text-2xl font-semibold mb-2">Performance Analytics</h2>
            <p className="text-slate-400">Monitor agent performance and system metrics</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;