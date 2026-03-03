"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { SearchResult } from "@/types";

interface AnswerViewProps {
  answer: string;
  results: SearchResult[];
}

export function AnswerView({ answer, results }: AnswerViewProps) {
  return (
    <div data-testid="answer-view" className="space-y-4">
      {/* Answer */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">최종 답변</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="whitespace-pre-wrap text-sm leading-relaxed">
            {answer}
          </div>
        </CardContent>
      </Card>

      {/* Reference documents */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            참조 문서
            <Badge variant="secondary">{results.length}건</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {results.map((doc, index) => (
            <div key={doc.chunk_id}>
              {index > 0 && <Separator className="mb-3" />}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {index + 1}. {(doc.metadata?.filename as string) ?? "알 수 없는 문서"}
                  </span>
                  <Badge variant="outline">
                    점수: {doc.score?.toFixed(4) ?? "-"}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  청크 ID: {doc.chunk_id}
                </p>
                <p className="rounded-md bg-muted p-3 text-sm leading-relaxed">
                  {doc.content}
                </p>
              </div>
            </div>
          ))}
          {results.length === 0 && (
            <p className="text-sm text-muted-foreground">참조 문서가 없습니다.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
