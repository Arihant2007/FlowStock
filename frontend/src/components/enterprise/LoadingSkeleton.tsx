
export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="w-full space-y-3 p-4 bg-white rounded-2xl border border-slate-100 animate-pulse">
      <div className="h-8 bg-slate-100 rounded-xl w-full mb-4" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 py-2">
          <div className="h-4 bg-slate-100 rounded-lg flex-1" />
          <div className="h-4 bg-slate-100 rounded-lg w-24" />
          <div className="h-4 bg-slate-100 rounded-lg w-16" />
          <div className="h-4 bg-slate-100 rounded-lg w-20" />
        </div>
      ))}
    </div>
  )
}

export function CardSkeleton() {
  return (
    <div className="rounded-2xl bg-white p-5 shadow-sm border border-slate-100 animate-pulse space-y-3">
      <div className="flex justify-between items-center">
        <div className="h-3 bg-slate-100 rounded w-24" />
        <div className="h-10 w-10 bg-slate-100 rounded-xl" />
      </div>
      <div className="h-8 bg-slate-100 rounded-lg w-32" />
      <div className="h-3 bg-slate-100 rounded w-20" />
    </div>
  )
}
