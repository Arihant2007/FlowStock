import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { inventoryApi } from '@/api/inventory'
import { masterApi } from '@/api/master'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { getErrorMessage } from '@/lib/utils'
import { ClipboardList, Plus, Trash2 } from 'lucide-react'
import { format } from 'date-fns'

const countItemSchema = z.object({
  material_public_id: z.string().min(1, 'Select a material'),
  actual_quantity: z.string().refine((v) => !isNaN(Number(v)) && Number(v) > 0, 'Must be > 0'),
})

const eodCountSchema = z.object({
  count_date: z.string().min(1, 'Date is required'),
  warehouse_public_id: z.string().min(1, 'Select a warehouse'),
  items: z.array(countItemSchema).min(1, 'Add at least one item'),
})

type EODCountForm = z.infer<typeof eodCountSchema>

export function EODCountPage() {
  const qc = useQueryClient()
  const today = format(new Date(), 'yyyy-MM-dd')

  const { register, control, handleSubmit, formState: { errors, isSubmitting }, setValue, watch, reset } = useForm<EODCountForm>({
    resolver: zodResolver(eodCountSchema),
    defaultValues: {
      count_date: today,
      items: [{ material_public_id: '', actual_quantity: '' }],
    },
  })

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'items',
  })

  const watchWarehouse = watch('warehouse_public_id')

  const { data: whData } = useQuery({
    queryKey: ['master', 'warehouses'],
    queryFn: () => masterApi.listWarehouses(1, 100),
  })

  const { data: matData } = useQuery({
    queryKey: ['master', 'materials'],
    queryFn: () => masterApi.listMaterials(1, 1000),
  })

  const mutation = useMutation({
    mutationFn: (data: EODCountForm) => {
      const payload = {
        count_date: data.count_date,
        items: data.items.map(item => ({
          material_public_id: item.material_public_id,
          warehouse_public_id: data.warehouse_public_id,
          actual_quantity: item.actual_quantity,
        })),
      }
      return inventoryApi.submitEODCount(payload)
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['inventory'] })
      const adjCount = (res.data as any).adjustments?.length || 0
      toast.success(`EOD count submitted. ${adjCount} adjustment(s) created.`)
      reset({
        count_date: today,
        warehouse_public_id: '',
        items: [{ material_public_id: '', actual_quantity: '' }],
      })
    },
    onError: (err) => toast.error(getErrorMessage(err)),
  })

  const warehouses = whData?.data ?? []
  const materials = matData?.data ?? []

  return (
    <div className="space-y-4 animate-fade-in max-w-4xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <ClipboardList className="h-6 w-6" /> End of Day Count
        </h1>
        <p className="text-muted-foreground text-sm">Submit physical inventory counts to automatically reconcile balances</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Count Details</CardTitle>
          <CardDescription>Select the warehouse and record physical quantities.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit((d) => mutation.mutate(d))} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Count Date</Label>
                <Input type="date" {...register('count_date')} />
                {errors.count_date && <p className="text-xs text-destructive">{errors.count_date.message}</p>}
              </div>
              <div className="space-y-1.5">
                <Label>Warehouse</Label>
                <Select value={watchWarehouse} onValueChange={(v) => setValue('warehouse_public_id', v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select warehouse..." />
                  </SelectTrigger>
                  <SelectContent>
                    {warehouses.map((w) => (
                      <SelectItem key={w.public_id} value={w.public_id}>{w.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.warehouse_public_id && <p className="text-xs text-destructive">{errors.warehouse_public_id.message}</p>}
              </div>
            </div>

            <div className="space-y-3 border-t pt-4">
              <div className="flex items-center justify-between">
                <Label className="text-base">Materials Counted</Label>
                <Button type="button" variant="outline" size="sm" onClick={() => append({ material_public_id: '', actual_quantity: '' })}>
                  <Plus className="h-4 w-4 mr-1" /> Add Row
                </Button>
              </div>

              {fields.map((field, index) => (
                <div key={field.id} className="flex gap-2 items-start">
                  <div className="flex-1 space-y-1.5">
                    <Select
                      value={watch(`items.${index}.material_public_id`)}
                      onValueChange={(v) => setValue(`items.${index}.material_public_id`, v)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select material..." />
                      </SelectTrigger>
                      <SelectContent>
                        {materials.map((m) => (
                          <SelectItem key={m.public_id} value={m.public_id}>
                            {m.name} <span className="text-muted-foreground ml-1">({m.code})</span>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    {errors.items?.[index]?.material_public_id && (
                      <p className="text-xs text-destructive">{errors.items[index]?.material_public_id?.message}</p>
                    )}
                  </div>
                  <div className="w-32 space-y-1.5">
                    <Input placeholder="Qty" {...register(`items.${index}.actual_quantity`)} />
                    {errors.items?.[index]?.actual_quantity && (
                      <p className="text-xs text-destructive">{errors.items[index]?.actual_quantity?.message}</p>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="text-destructive hover:text-destructive shrink-0"
                    onClick={() => remove(index)}
                    disabled={fields.length === 1}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              {errors.items?.root && <p className="text-xs text-destructive">{errors.items.root.message}</p>}
            </div>

            <Button type="submit" className="w-full" isLoading={isSubmitting || mutation.isPending}>
              Submit EOD Count
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
