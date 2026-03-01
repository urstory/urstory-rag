"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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

const generationSchema = z.object({
  provider: z.string(),
  model: z.string().min(1),
  system_prompt: z.string(),
  temperature: z.number().min(0).max(2),
  max_tokens: z.number().min(1).max(8192),
});

type GenerationFormData = z.infer<typeof generationSchema>;

export function GenerationForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<GenerationFormData>({
    resolver: zodResolver(generationSchema),
    values: settings?.generation ?? {
      provider: "ollama",
      model: "qwen2.5:7b",
      system_prompt:
        "당신은 사내 문서를 기반으로 질문에 답변하는 AI 어시스턴트입니다.",
      temperature: 0.1,
      max_tokens: 1024,
    },
  });

  const onSubmit = async (data: GenerationFormData) => {
    try {
      await updateMutation.mutateAsync({ generation: data });
      toast.success("답변 생성 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  const temperature = form.watch("temperature");

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

          <div className="space-y-2">
            <Label>Temperature: {temperature.toFixed(2)}</Label>
            <Slider
              value={[temperature]}
              onValueChange={(v) => form.setValue("temperature", v[0])}
              min={0}
              max={2}
              step={0.05}
            />
            <p className="text-xs text-muted-foreground">
              낮을수록 결정적, 높을수록 창의적
            </p>
          </div>

          <div className="space-y-2">
            <Label>최대 토큰</Label>
            <Input
              type="number"
              value={form.watch("max_tokens")}
              onChange={(e) => form.setValue("max_tokens", Number(e.target.value))}
              min={1}
              max={8192}
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
