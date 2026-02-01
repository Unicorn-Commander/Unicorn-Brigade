export default function ListSkeleton({ rows = 5 }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center space-x-4 bg-slate-800/30 rounded-lg p-4 animate-pulse"
        >
          <div className="w-10 h-10 bg-slate-700/50 rounded-full" />
          <div className="flex-1 space-y-2">
            <div className="h-4 bg-slate-700/50 rounded w-1/3" />
            <div className="h-3 bg-slate-700/50 rounded w-1/2" />
          </div>
          <div className="w-20 h-8 bg-slate-700/50 rounded" />
        </div>
      ))}
    </div>
  );
}
