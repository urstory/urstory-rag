"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
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

const chunkingSchema = z.object({
  strategy: z.string(),
  chunk_size: z.number().min(100).max(2000),
  chunk_overlap: z.number().min(0).max(500),
});

type ChunkingFormData = z.infer<typeof chunkingSchema>;

export function ChunkingForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<ChunkingFormData>({
    resolver: zodResolver(chunkingSchema),
    values: settings?.chunking ?? {
      strategy: "recursive",
      chunk_size: 512,
      chunk_overlap: 50,
    },
  });

  const onSubmit = async (data: ChunkingFormData) => {
    try {
      await updateMutation.mutateAsync({ chunking: data });
      toast.success("청킹 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  const chunkSize = form.watch("chunk_size");
  const chunkOverlap = form.watch("chunk_overlap");

  return (
    <Card>
      <CardHeader>
        <CardTitle>청킹 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-2">
            <Label>청킹 전략</Label>
            <Select
              value={form.watch("strategy")}
              onValueChange={(v) => form.setValue("strategy", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="recursive">Recursive</SelectItem>
                <SelectItem value="sentence">Sentence</SelectItem>
                <SelectItem value="token">Token</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>청크 크기: {chunkSize}</Label>
            <Slider
              value={[chunkSize]}
              onValueChange={(v) => form.setValue("chunk_size", v[0])}
              min={100}
              max={2000}
              step={50}
            />
            <p className="text-xs text-muted-foreground">100 ~ 2000</p>
          </div>

          <div className="space-y-2">
            <Label>청크 오버랩: {chunkOverlap}</Label>
            <Slider
              value={[chunkOverlap]}
              onValueChange={(v) => form.setValue("chunk_overlap", v[0])}
              min={0}
              max={500}
              step={10}
            />
            <p className="text-xs text-muted-foreground">0 ~ 500</p>
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
