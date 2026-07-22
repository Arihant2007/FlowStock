import { useMemo } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Activity } from 'lucide-react'

interface TrendsChartProps {
  data: {
    dates: string[]
    dispatch: number[]
    receipt: number[]
    adjustment: number[]
    reservation: number[]
    netMovement: number[]
  } | undefined
  isLoading: boolean
  isError: boolean
}

export function TrendsChart({ data, isLoading, isError }: TrendsChartProps) {
  const chartData = useMemo(() => {
    if (!data || !data.dates) return []
    return data.dates.map((date, i) => ({
      date: new Date(date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      dispatch: data.dispatch[i],
      receipt: data.receipt[i],
      adjustment: data.adjustment[i],
      reservation: data.reservation[i],
      netMovement: data.netMovement[i],
    }))
  }, [data])

  if (isLoading) {
    return (
      <div className="h-[350px] w-full flex items-center justify-center bg-slate-50/50 rounded-xl border border-slate-100">
        <div className="flex flex-col items-center text-slate-400">
          <Activity className="h-8 w-8 animate-pulse mb-2" />
          <p className="text-sm">Loading trends...</p>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="h-[350px] w-full flex items-center justify-center bg-red-50/50 rounded-xl border border-red-100">
        <p className="text-sm text-red-600 font-medium">Failed to load inventory trends.</p>
      </div>
    )
  }

  if (chartData.length === 0) {
    return (
      <div className="h-[350px] w-full flex items-center justify-center bg-slate-50/50 rounded-xl border border-slate-100">
        <p className="text-sm text-slate-500">No data available for the selected period.</p>
      </div>
    )
  }

  return (
    <div className="h-[350px] w-full mt-4">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart
          data={chartData}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorReceipt" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorDispatch" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="colorNet" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
          <XAxis 
            dataKey="date" 
            tick={{ fontSize: 12, fill: '#64748b' }} 
            tickMargin={10} 
            axisLine={false} 
            tickLine={false}
          />
          <YAxis 
            tick={{ fontSize: 12, fill: '#64748b' }} 
            tickMargin={10} 
            axisLine={false} 
            tickLine={false}
            tickFormatter={(val) => val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val}
          />
          <Tooltip 
            contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)' }}
            labelStyle={{ fontWeight: 'bold', color: '#0f172a', marginBottom: '4px' }}
          />
          <Legend wrapperStyle={{ paddingTop: '20px' }} />
          <Area 
            type="monotone" 
            dataKey="receipt" 
            name="Receipts"
            stroke="#10b981" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorReceipt)" 
          />
          <Area 
            type="monotone" 
            dataKey="dispatch" 
            name="Dispatches"
            stroke="#ef4444" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorDispatch)" 
          />
          <Area 
            type="monotone" 
            dataKey="netMovement" 
            name="Net Movement"
            stroke="#3b82f6" 
            strokeWidth={2}
            fillOpacity={1} 
            fill="url(#colorNet)" 
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
