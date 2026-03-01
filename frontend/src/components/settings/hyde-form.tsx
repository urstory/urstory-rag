"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useSettings, useUpdateSettings } from "@/lib/queries";
import { toast } from "sonner";
import { Save } from "lucide-react";

const hydeSchema = z.object({
  enabled: z.boolean(),
  model: z.string().min(1),
  apply_mode: z.enum(["all", "long_query", "complex"]),
});

type HyDEFormData = z.infer<typeof hydeSchema>;

export function HyDEForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<HyDEFormData>({
    resolver: zodResolver(hydeSchema),
    values: settings?.hyde ?? {
      enabled: true,
      model: "qwen2.5:7b",
      apply_mode: "all",
    },
  });

  const onSubmit = async (data: HyDEFormData) => {
    try {
      await updateMutation.mutateAsync({ hyde: data });
      toast.success("HyDE 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>HyDE 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="flex items-center justify-between">
            <Label>HyDE 활성화</Label>
            <Switch
              checked={form.watch("enabled")}
              onCheckedChange={(v) => form.setValue("enabled", v)}
            />
          </div>

          <div className="space-y-2">
            <Label>모델</Label>
            <Input
              {...form.register("model")}
              placeholder="qwen2.5:7b"
            />
            {form.formState.errors.model && (
              <p className="text-xs text-destructive">{form.formState.errors.model.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>적용 모드</Label>
            <Select
              value={form.watch("apply_mode")}
              onValueChange={(v) => form.setValue("apply_mode", v as HyDEFormData["apply_mode"])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">전체 쿼리</SelectItem>
                <SelectItem value="long_query">긴 쿼리만</SelectItem>
                <SelectItem value="complex">복잡한 쿼리만</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Button type="submit" disabled={updateMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {updateMutation.isPending ? "저장 중..." : "저장"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
