"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
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

const embeddingSchema = z.object({
  provider: z.string(),
  model: z.string().min(1),
});

type EmbeddingFormData = z.infer<typeof embeddingSchema>;

export function EmbeddingForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<EmbeddingFormData>({
    resolver: zodResolver(embeddingSchema),
    values: settings?.embedding ?? {
      provider: "ollama",
      model: "bge-m3",
    },
  });

  const onSubmit = async (data: EmbeddingFormData) => {
    try {
      await updateMutation.mutateAsync({ embedding: data });
      toast.success("임베딩 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>임베딩 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-2">
            <Label>프로바이더</Label>
            <Select
              value={form.watch("provider")}
              onValueChange={(v) => form.setValue("provider", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ollama">Ollama</SelectItem>
                <SelectItem value="openai">OpenAI</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>모델</Label>
            <Input
              {...form.register("model")}
              placeholder="bge-m3"
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
