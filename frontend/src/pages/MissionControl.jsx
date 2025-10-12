import { Target, Play, Pause, AlertCircle } from 'lucide-react';

const MissionControl = () => {
  return (
    <div className="p-6">
      <h1 className="text-3xl font-bold text-gradient mb-6">Mission Control</h1>
      <div className="card">
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <Target className="w-16 h-16 text-unicorn-400 mx-auto mb-4" />
            <h2 className="text-2xl font-semibold mb-2">Workflow Designer</h2>
            <p className="text-slate-400">Create and manage agent workflows</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MissionControl;