"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Clock } from "lucide-react";
import type { PipelineStep } from "@/types";

interface PipelineTraceViewProps {
  steps: PipelineStep[];
}

const STEP_LABELS: Record<string, string> = {
  guardrail_input: "가드레일 (입력)",
  question_classification: "질문 분류",
  multi_query: "멀티쿼리 생성",
  hyde: "HyDE 가상 문서 생성",
  vector_search: "벡터 검색",
  keyword_search: "키워드 검색",
  cascading_eval_stage1: "BM25 품질 평가",
  query_expansion: "쿼리 확장",
  keyword_search_expanded: "확장 키워드 재검색",
  cascading_eval_stage2: "확장 결과 품질 평가",
  cascading_vector_fallback: "벡터 폴백 (RRF)",
  rrf_fusion: "RRF 결합",
  document_scope: "문서 스코프 선택",
  reranking: "리랭킹",
  retrieval_gate: "검색 품질 게이트",
  guardrail_pii: "가드레일 (PII)",
  evidence_extraction: "근거 추출",
  generation: "답변 생성",
  numeric_verification: "숫자 검증",
  guardrail_faithfulness: "가드레일 (Faithfulness)",
  guardrail_hallucination: "가드레일 (할루시네이션)",
};

function StepDetail({ step }: { step: PipelineStep }) {
  const details: string[] = [];

  if (step.results_count != null) details.push(`결과: ${step.results_count}건`);

  if (step.detail) {
    const d = step.detail;
    if (d.category) details.push(`분류: ${d.category}`);
    if (Array.isArray(d.variants)) details.push(`쿼리 변형: ${d.variants.length}개`);
    if (d.generated_length) details.push(`생성 길이: ${d.generated_length}자`);
    if (d.top_score != null) details.push(`최고 점수: ${Number(d.top_score).toFixed(4)}`);
    if (d.pii_found != null) details.push(`PII 탐지: ${d.pii_found ? "발견" : "없음"}`);
    if (d.faithfulness_score != null) details.push(`Faithfulness: ${Number(d.faithfulness_score).toFixed(2)}`);
    if (d.grounded_ratio != null) details.push(`Grounded: ${Number(d.grounded_ratio).toFixed(2)}`);
    if (d.before != null && d.after != null) details.push(`필터: ${d.before} → ${d.after}`);
    if (d.total_numbers != null) details.push(`숫자 검증: ${d.total_numbers}개`);
  }

  if (details.length === 0) return null;

  return (
    <div className="mt-2 space-y-1 text-sm text-muted-foreground">
      {details.map((text, i) => (
        <p key={i}>{text}</p>
      ))}
    </div>
  );
}

export function PipelineTraceView({ steps }: PipelineTraceViewProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

  const totalDuration = steps.reduce((sum, s) => sum + s.duration_ms, 0);

  const toggleStep = (index: number) => {
    const next = new Set(expandedSteps);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    setExpandedSteps(next);
  };

  return (
    <Card data-testid="pipeline-trace">
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>파이프라인 실행 결과</span>
          <Badge variant="outline">
            <Clock className="mr-1 h-3 w-3" />
            총 {(totalDuration / 1000).toFixed(2)}s
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {steps.map((step, index) => {
            const isExpanded = expandedSteps.has(index);
            return (
              <div key={index}>
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 px-2"
                  onClick={() => toggleStep(index)}
                >
                  <span className="text-xs text-muted-foreground w-4">{index + 1}.</span>
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <span className="flex-1 text-left text-sm">
                    {STEP_LABELS[step.name] ?? step.name}
                  </span>
                  {step.passed ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-600" />
                  )}
                  <span className="text-xs text-muted-foreground">
                    {step.duration_ms >= 1000
                      ? `${(step.duration_ms / 1000).toFixed(2)}s`
                      : `${step.duration_ms.toFixed(0)}ms`}
                  </span>
                </Button>
                {isExpanded && (
                  <div className="ml-12 pb-2">
                    <StepDetail step={step} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
