"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Separator } from "@/components/ui/separator";
import { useSettings, useUpdateSettings } from "@/lib/queries";
import { toast } from "sonner";
import { Save } from "lucide-react";

const guardrailsSchema = z.object({
  pii_detection: z.boolean(),
  injection_detection: z.boolean(),
  hallucination_detection: z.boolean(),
  exact_citation: z.boolean(),
  numeric_verification: z.boolean(),
});

type GuardrailsFormData = z.infer<typeof guardrailsSchema>;

export function GuardrailsForm() {
  const { data: settings, isLoading, isError } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<GuardrailsFormData>({
    resolver: zodResolver(guardrailsSchema),
    values: {
      pii_detection: settings?.pii_detection_enabled ?? true,
      injection_detection: settings?.injection_detection_enabled ?? true,
      hallucination_detection: settings?.hallucination_detection_enabled ?? true,
      exact_citation: settings?.exact_citation_enabled ?? true,
      numeric_verification: settings?.numeric_verification_enabled ?? true,
    },
  });

  const onSubmit = async (data: GuardrailsFormData) => {
    try {
      await updateMutation.mutateAsync({
        pii_detection_enabled: data.pii_detection,
        injection_detection_enabled: data.injection_detection,
        hallucination_detection_enabled: data.hallucination_detection,
        exact_citation_enabled: data.exact_citation,
        numeric_verification_enabled: data.numeric_verification,
      });
      toast.success("가드레일 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;
  if (isError) return <p className="text-destructive">설정을 불러올 수 없습니다.</p>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>가드레일 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label>PII 탐지</Label>
                <p className="text-xs text-muted-foreground">
                  개인정보(이름, 전화번호, 이메일 등) 자동 탐지 및 마스킹
                </p>
              </div>
              <Switch
                checked={form.watch("pii_detection")}
                onCheckedChange={(v) => form.setValue("pii_detection", v)}
              />
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <Label>프롬프트 인젝션 탐지</Label>
                <p className="text-xs text-muted-foreground">
                  악의적인 프롬프트 주입 시도 탐지 및 차단
                </p>
              </div>
              <Switch
                checked={form.watch("injection_detection")}
                onCheckedChange={(v) => form.setValue("injection_detection", v)}
              />
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <Label>할루시네이션 탐지</Label>
                <p className="text-xs text-muted-foreground">
                  생성된 답변의 사실성을 참조 문서 기반으로 검증
                </p>
              </div>
              <Switch
                checked={form.watch("hallucination_detection")}
                onCheckedChange={(v) => form.setValue("hallucination_detection", v)}
              />
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <Label>정확 인용 모드</Label>
                <p className="text-xs text-muted-foreground">
                  규정형 질문(횟수, 기간 등)에 대해 근거 기반 답변 생성
                </p>
              </div>
              <Switch
                checked={form.watch("exact_citation")}
                onCheckedChange={(v) => form.setValue("exact_citation", v)}
              />
            </div>

            <Separator />

            <div className="flex items-center justify-between">
              <div>
                <Label>숫자 검증</Label>
                <p className="text-xs text-muted-foreground">
                  답변의 숫자가 참조 문서에 존재하는지 검증
                </p>
              </div>
              <Switch
                checked={form.watch("numeric_verification")}
                onCheckedChange={(v) => form.setValue("numeric_verification", v)}
              />
            </div>
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
