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

const rerankingSchema = z.object({
  enabled: z.boolean(),
  model: z.string().min(1),
  top_k: z.number().min(1).max(50),
  retriever_top_k: z.number().min(1).max(100),
});

type RerankingFormData = z.infer<typeof rerankingSchema>;

export function RerankingForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<RerankingFormData>({
    resolver: zodResolver(rerankingSchema),
    values: settings?.reranking ?? {
      enabled: true,
      model: "dragonkue/bge-reranker-v2-m3-ko",
      top_k: 5,
      retriever_top_k: 20,
    },
  });

  const onSubmit = async (data: RerankingFormData) => {
    try {
      await updateMutation.mutateAsync({ reranking: data });
      toast.success("리랭킹 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>리랭킹 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="flex items-center justify-between">
            <Label>리랭킹 활성화</Label>
            <Switch
              checked={form.watch("enabled")}
              onCheckedChange={(v) => form.setValue("enabled", v)}
            />
          </div>

          <div className="space-y-2">
            <Label>모델</Label>
            <Input
              {...form.register("model")}
              placeholder="dragonkue/bge-reranker-v2-m3-ko"
            />
            {form.formState.errors.model && (
              <p className="text-xs text-destructive">{form.formState.errors.model.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Retriever Top-K</Label>
            <Input
              type="number"
              value={form.watch("retriever_top_k")}
              onChange={(e) => form.setValue("retriever_top_k", Number(e.target.value))}
              min={1}
              max={100}
            />
            <p className="text-xs text-muted-foreground">초기 검색에서 가져올 문서 수</p>
          </div>

          <div className="space-y-2">
            <Label>Reranker Top-K</Label>
            <Input
              type="number"
              value={form.watch("top_k")}
              onChange={(e) => form.setValue("top_k", Number(e.target.value))}
              min={1}
              max={50}
            />
            <p className="text-xs text-muted-foreground">리랭킹 후 최종 반환 문서 수</p>
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
