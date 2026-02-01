export default function StatsSkeleton({ count = 4 }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 rounded-xl p-6 animate-pulse"
        >
          <div className="flex items-center justify-between mb-4">
            <div className="w-10 h-10 bg-slate-700/50 rounded-lg" />
            <div className="w-16 h-6 bg-slate-700/50 rounded" />
          </div>
          <div className="h-8 bg-slate-700/50 rounded w-20 mb-2" />
          <div className="h-3 bg-slate-700/50 rounded w-24" />
        </div>
      ))}
    </div>
  );
}
