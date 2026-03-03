"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

const generationSchema = z.object({
  provider: z.string(),
  model: z.string().min(1),
  system_prompt: z.string(),
});

type GenerationFormData = z.infer<typeof generationSchema>;

export function GenerationForm() {
  const { data: settings, isLoading, isError } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<GenerationFormData>({
    resolver: zodResolver(generationSchema),
    values: {
      provider: settings?.llm_provider ?? "openai",
      model: settings?.llm_model ?? "gpt-4.1-mini",
      system_prompt: settings?.system_prompt ?? "당신은 사내 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.",
    },
  });

  const onSubmit = async (data: GenerationFormData) => {
    try {
      await updateMutation.mutateAsync({
        llm_provider: data.provider,
        llm_model: data.model,
        system_prompt: data.system_prompt,
      });
      toast.success("답변 생성 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;
  if (isError) return <p className="text-destructive">설정을 불러올 수 없습니다.</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>답변 생성 설정</CardTitle>
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
                <SelectItem value="anthropic">Anthropic</SelectItem>
              </SelectContent>
            </Select>
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
            <Label>시스템 프롬프트</Label>
            <Textarea
              {...form.register("system_prompt")}
              rows={4}
              placeholder="시스템 프롬프트를 입력하세요..."
            />
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
