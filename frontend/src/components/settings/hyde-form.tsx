"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useSettings, useUpdateSettings } from "@/lib/queries";
import { toast } from "sonner";
import { Save } from "lucide-react";

const hydeSchema = z.object({
  enabled: z.boolean(),
  model: z.string().min(1),
});

type HyDEFormData = z.infer<typeof hydeSchema>;

export function HyDEForm() {
  const { data: settings, isLoading, isError } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<HyDEFormData>({
    resolver: zodResolver(hydeSchema),
    values: {
      enabled: settings?.hyde_enabled ?? true,
      model: settings?.hyde_model ?? "gpt-4.1-mini",
    },
  });

  const onSubmit = async (data: HyDEFormData) => {
    try {
      await updateMutation.mutateAsync({
        hyde_enabled: data.enabled,
        hyde_model: data.model,
      });
      toast.success("HyDE 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;
  if (isError) return <p className="text-destructive">설정을 불러올 수 없습니다.</p>;

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

          <Button type="submit" disabled={updateMutation.isPending}>
            <Save className="mr-2 h-4 w-4" />
            {updateMutation.isPending ? "저장 중..." : "저장"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
