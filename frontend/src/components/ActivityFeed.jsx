import { AlertCircle, CheckCircle, Info, AlertTriangle, Clock } from 'lucide-react';

const ActivityFeed = ({ activities }) => {
  const getIcon = (status) => {
    switch(status) {
      case 'success':
        return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case 'warning':
        return <AlertTriangle className="w-4 h-4 text-amber-400" />;
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-400" />;
      default:
        return <Info className="w-4 h-4 text-cyan-400" />;
    }
  };

  return (
    <div className="card h-full">
      <h2 className="text-xl font-semibold mb-4">Activity Feed</h2>
      <div className="space-y-3 max-h-96 overflow-y-auto scrollbar-thin">
        {activities.map((activity) => (
          <div key={activity.id} className="flex items-start space-x-3 p-3 rounded-lg bg-slate-900/30">
            <div className="mt-1">
              {getIcon(activity.status)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-slate-200">{activity.message}</p>
              <div className="flex items-center space-x-2 mt-1">
                <Clock className="w-3 h-3 text-slate-500" />
                <span className="text-xs text-slate-500">{activity.time}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ActivityFeed;