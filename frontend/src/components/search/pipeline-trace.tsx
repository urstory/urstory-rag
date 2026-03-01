"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, CheckCircle2, XCircle, Clock } from "lucide-react";
import type { PipelineTrace, PipelineStep } from "@/types";

interface PipelineTraceViewProps {
  trace: PipelineTrace;
}

interface StepInfo {
  key: string;
  label: string;
  step: PipelineStep;
}

function getSteps(trace: PipelineTrace): StepInfo[] {
  const steps: StepInfo[] = [];

  if (trace.guardrail_input) {
    steps.push({ key: "guardrail_input", label: "가드레일 (입력)", step: trace.guardrail_input });
  }
  if (trace.hyde) {
    steps.push({ key: "hyde", label: "HyDE 가상 문서 생성", step: trace.hyde });
  }
  if (trace.vector_search) {
    steps.push({ key: "vector_search", label: "벡터 검색", step: trace.vector_search });
  }
  if (trace.keyword_search) {
    steps.push({ key: "keyword_search", label: "키워드 검색", step: trace.keyword_search });
  }
  if (trace.rrf_fusion) {
    steps.push({ key: "rrf_fusion", label: "RRF 결합", step: trace.rrf_fusion });
  }
  if (trace.reranking) {
    steps.push({ key: "reranking", label: "리랭킹", step: trace.reranking });
  }
  if (trace.guardrail_pii) {
    steps.push({ key: "guardrail_pii", label: "가드레일 (PII)", step: trace.guardrail_pii });
  }
  if (trace.generation) {
    steps.push({ key: "generation", label: "답변 생성", step: trace.generation });
  }
  if (trace.guardrail_hallucination) {
    steps.push({ key: "guardrail_hallucination", label: "가드레일 (할루시네이션)", step: trace.guardrail_hallucination });
  }

  return steps;
}

function StepDetail({ step }: { step: PipelineStep }) {
  const details: string[] = [];

  if (step.results_count !== undefined) details.push(`결과: ${step.results_count}건`);
  if (step.input_count !== undefined) details.push(`입력: ${step.input_count}건`);
  if (step.output_count !== undefined) details.push(`출력: ${step.output_count}건`);
  if (step.model) details.push(`모델: ${step.model}`);
  if (step.confidence !== undefined) details.push(`신뢰도: ${(step.confidence * 100).toFixed(1)}%`);
  if (step.tokens) {
    details.push(`토큰: ${step.tokens.prompt} (입력) / ${step.tokens.completion} (출력)`);
  }
  if (step.generated_document) {
    details.push(`생성 문서: ${step.generated_document.substring(0, 100)}...`);
  }

  return (
    <div className="mt-2 space-y-1 text-sm text-muted-foreground">
      {details.map((d, i) => (
        <p key={i}>{d}</p>
      ))}
    </div>
  );
}

export function PipelineTraceView({ trace }: PipelineTraceViewProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const steps = getSteps(trace);

  const toggleStep = (key: string) => {
    const next = new Set(expandedSteps);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setExpandedSteps(next);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between text-base">
          <span>파이프라인 실행 결과</span>
          <Badge variant="outline">
            <Clock className="mr-1 h-3 w-3" />
            총 {(trace.total_duration_ms / 1000).toFixed(2)}s
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {steps.map(({ key, label, step }, index) => {
            const isExpanded = expandedSteps.has(key);
            const passed = step.passed !== false;
            return (
              <div key={key}>
                <Button
                  variant="ghost"
                  className="w-full justify-start gap-2 px-2"
                  onClick={() => toggleStep(key)}
                >
                  <span className="text-xs text-muted-foreground w-4">{index + 1}.</span>
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                  <span className="flex-1 text-left text-sm">{label}</span>
                  {passed ? (
                    <CheckCircle2 className="h-4 w-4 text-green-600" />
                  ) : (
                    <XCircle className="h-4 w-4 text-red-600" />
                  )}
                  {step.duration_ms !== undefined && (
                    <span className="text-xs text-muted-foreground">
                      {step.duration_ms}ms
                    </span>
                  )}
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
