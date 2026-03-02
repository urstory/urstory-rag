"use client";

import { useForm } from "react-hook-form";
import { z } from "zod/v4";
import { zodResolver } from "@hookform/resolvers/zod";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
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

const searchSchema = z.object({
  mode: z.enum(["hybrid", "vector", "keyword", "cascading"]),
  keyword_engine: z.string(),
  rrf_constant: z.number().min(1).max(200),
  vector_weight: z.number().min(0).max(1),
  keyword_weight: z.number().min(0).max(1),
  cascading_bm25_threshold: z.number().min(0.5).max(20),
  cascading_min_qualifying_docs: z.number().min(1).max(10),
  cascading_min_doc_score: z.number().min(0.1).max(10),
  cascading_fallback_vector_weight: z.number().min(0).max(1),
  cascading_fallback_keyword_weight: z.number().min(0).max(1),
  query_expansion_enabled: z.boolean(),
  query_expansion_max_keywords: z.number().min(3).max(20),
  multi_query_enabled: z.boolean(),
  multi_query_count: z.number().min(2).max(8),
});

type SearchFormData = z.infer<typeof searchSchema>;

export function SearchForm() {
  const { data: settings, isLoading } = useSettings();
  const updateMutation = useUpdateSettings();

  const form = useForm<SearchFormData>({
    resolver: zodResolver(searchSchema),
    values: settings?.search ?? {
      mode: "hybrid",
      keyword_engine: "elasticsearch",
      rrf_constant: 60,
      vector_weight: 0.5,
      keyword_weight: 0.5,
      cascading_bm25_threshold: 3.0,
      cascading_min_qualifying_docs: 3,
      cascading_min_doc_score: 1.0,
      cascading_fallback_vector_weight: 0.3,
      cascading_fallback_keyword_weight: 0.7,
      query_expansion_enabled: true,
      query_expansion_max_keywords: 10,
      multi_query_enabled: true,
      multi_query_count: 4,
    },
  });

  const onSubmit = async (data: SearchFormData) => {
    try {
      await updateMutation.mutateAsync({ search: data });
      toast.success("검색 설정이 저장되었습니다.");
    } catch {
      toast.error("설정 저장에 실패했습니다.");
    }
  };

  if (isLoading) return <p className="text-muted-foreground">로딩 중...</p>;

  const mode = form.watch("mode");
  const vectorWeight = form.watch("vector_weight");
  const keywordWeight = form.watch("keyword_weight");
  const rrfConstant = form.watch("rrf_constant");
  const cascadingThreshold = form.watch("cascading_bm25_threshold");
  const cascadingMinDocs = form.watch("cascading_min_qualifying_docs");
  const cascadingMinDocScore = form.watch("cascading_min_doc_score");
  const cascadingVectorWeight = form.watch("cascading_fallback_vector_weight");
  const cascadingKeywordWeight = form.watch("cascading_fallback_keyword_weight");
  const queryExpansionEnabled = form.watch("query_expansion_enabled");
  const queryExpansionMaxKeywords = form.watch("query_expansion_max_keywords");
  const multiQueryEnabled = form.watch("multi_query_enabled");
  const multiQueryCount = form.watch("multi_query_count");

  return (
    <Card>
      <CardHeader>
        <CardTitle>검색 설정</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
          <div className="space-y-2">
            <Label>검색 모드</Label>
            <Select
              value={mode}
              onValueChange={(v) => form.setValue("mode", v as SearchFormData["mode"])}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="cascading">캐스케이딩 (BM25 우선)</SelectItem>
                <SelectItem value="hybrid">하이브리드 (RRF)</SelectItem>
                <SelectItem value="vector">벡터</SelectItem>
                <SelectItem value="keyword">키워드</SelectItem>
              </SelectContent>
            </Select>
            {mode === "cascading" && (
              <p className="text-xs text-muted-foreground">
                BM25 검색 우선, 불충분 시 쿼리 확장 후 재검색, 최후에 벡터 폴백
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label>키워드 엔진</Label>
            <Select
              value={form.watch("keyword_engine")}
              onValueChange={(v) => form.setValue("keyword_engine", v)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="elasticsearch">Elasticsearch (Nori)</SelectItem>
                <SelectItem value="bm25">BM25 (kiwipiepy)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Hybrid 모드 전용 설정 */}
          {mode === "hybrid" && (
            <>
              <div className="space-y-2">
                <Label>RRF Constant (k): {rrfConstant}</Label>
                <Input
                  type="number"
                  value={rrfConstant}
                  onChange={(e) => form.setValue("rrf_constant", Number(e.target.value))}
                  min={1}
                  max={200}
                />
              </div>

              <div className="space-y-2">
                <Label>벡터 가중치: {vectorWeight.toFixed(2)}</Label>
                <Slider
                  value={[vectorWeight]}
                  onValueChange={(v) => form.setValue("vector_weight", v[0])}
                  min={0}
                  max={1}
                  step={0.05}
                />
              </div>

              <div className="space-y-2">
                <Label>키워드 가중치: {keywordWeight.toFixed(2)}</Label>
                <Slider
                  value={[keywordWeight]}
                  onValueChange={(v) => form.setValue("keyword_weight", v[0])}
                  min={0}
                  max={1}
                  step={0.05}
                />
              </div>
            </>
          )}

          {/* Cascading 모드 전용 설정 */}
          {mode === "cascading" && (
            <>
              <div className="rounded-lg border p-4 space-y-4">
                <h4 className="text-sm font-medium">BM25 품질 판정</h4>

                <div className="space-y-2">
                  <Label>BM25 충분 판정 임계값: {cascadingThreshold.toFixed(1)}</Label>
                  <Slider
                    value={[cascadingThreshold]}
                    onValueChange={(v) => form.setValue("cascading_bm25_threshold", v[0])}
                    min={0.5}
                    max={20}
                    step={0.5}
                  />
                  <p className="text-xs text-muted-foreground">
                    ES BM25 top score가 이 값 이상이면 충분으로 판정
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>최소 유효 문서 수: {cascadingMinDocs}</Label>
                  <Input
                    type="number"
                    value={cascadingMinDocs}
                    onChange={(e) => form.setValue("cascading_min_qualifying_docs", Number(e.target.value))}
                    min={1}
                    max={10}
                  />
                </div>

                <div className="space-y-2">
                  <Label>유효 문서 최소 점수: {cascadingMinDocScore.toFixed(1)}</Label>
                  <Slider
                    value={[cascadingMinDocScore]}
                    onValueChange={(v) => form.setValue("cascading_min_doc_score", v[0])}
                    min={0.1}
                    max={10}
                    step={0.1}
                  />
                </div>
              </div>

              <div className="rounded-lg border p-4 space-y-4">
                <h4 className="text-sm font-medium">쿼리 확장 (HyDE)</h4>

                <div className="flex items-center justify-between">
                  <Label>쿼리 확장 활성화</Label>
                  <Switch
                    checked={queryExpansionEnabled}
                    onCheckedChange={(v) => form.setValue("query_expansion_enabled", v)}
                  />
                </div>

                {queryExpansionEnabled && (
                  <div className="space-y-2">
                    <Label>확장 키워드 최대 개수: {queryExpansionMaxKeywords}</Label>
                    <Input
                      type="number"
                      value={queryExpansionMaxKeywords}
                      onChange={(e) => form.setValue("query_expansion_max_keywords", Number(e.target.value))}
                      min={3}
                      max={20}
                    />
                  </div>
                )}
              </div>

              <div className="rounded-lg border p-4 space-y-4">
                <h4 className="text-sm font-medium">벡터 폴백 가중치</h4>
                <p className="text-xs text-muted-foreground">
                  BM25 + 쿼리 확장 모두 불충분 시 벡터 폴백에 적용되는 RRF 가중치
                </p>

                <div className="space-y-2">
                  <Label>키워드 가중치: {cascadingKeywordWeight.toFixed(2)}</Label>
                  <Slider
                    value={[cascadingKeywordWeight]}
                    onValueChange={(v) => form.setValue("cascading_fallback_keyword_weight", v[0])}
                    min={0}
                    max={1}
                    step={0.05}
                  />
                </div>

                <div className="space-y-2">
                  <Label>벡터 가중치: {cascadingVectorWeight.toFixed(2)}</Label>
                  <Slider
                    value={[cascadingVectorWeight]}
                    onValueChange={(v) => form.setValue("cascading_fallback_vector_weight", v[0])}
                    min={0}
                    max={1}
                    step={0.05}
                  />
                </div>
              </div>
            </>
          )}

          {/* 멀티쿼리 설정 (모든 모드 공통) */}
          <div className="rounded-lg border p-4 space-y-4">
            <h4 className="text-sm font-medium">멀티쿼리 검색</h4>
            <p className="text-xs text-muted-foreground">
              LLM으로 질문 변형을 생성하여 병렬 검색 후 결과를 합산합니다
            </p>

            <div className="flex items-center justify-between">
              <Label>멀티쿼리 활성화</Label>
              <Switch
                checked={multiQueryEnabled}
                onCheckedChange={(v) => form.setValue("multi_query_enabled", v)}
              />
            </div>

            {multiQueryEnabled && (
              <div className="space-y-2">
                <Label>쿼리 변형 수: {multiQueryCount}</Label>
                <Input
                  type="number"
                  value={multiQueryCount}
                  onChange={(e) => form.setValue("multi_query_count", Number(e.target.value))}
                  min={2}
                  max={8}
                />
                <p className="text-xs text-muted-foreground">
                  원본 포함 총 변형 수 (2~8, 기본 4)
                </p>
              </div>
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
