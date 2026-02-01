export default function CardSkeleton({ count = 1 }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 rounded-xl p-6 animate-pulse"
        >
          <div className="flex items-start space-x-4">
            <div className="w-12 h-12 bg-slate-700/50 rounded-lg" />
            <div className="flex-1 space-y-3">
              <div className="h-5 bg-slate-700/50 rounded w-3/4" />
              <div className="h-4 bg-slate-700/50 rounded w-1/2" />
            </div>
          </div>
          <div className="mt-4 space-y-2">
            <div className="h-3 bg-slate-700/50 rounded w-full" />
            <div className="h-3 bg-slate-700/50 rounded w-5/6" />
          </div>
        </div>
      ))}
    </>
  );
}
