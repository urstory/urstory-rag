"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import type { SearchResultDocument } from "@/types";

interface AnswerViewProps {
  answer: string;
  documents: SearchResultDocument[];
}

export function AnswerView({ answer, documents }: AnswerViewProps) {
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
            <Badge variant="secondary">{documents.length}건</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {documents.map((doc, index) => (
            <div key={doc.id}>
              {index > 0 && <Separator className="mb-3" />}
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {index + 1}. {doc.meta.doc_name}
                  </span>
                  <Badge variant="outline">
                    점수: {doc.score.toFixed(4)}
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  청크 #{doc.meta.chunk_index + 1}
                </p>
                <p className="rounded-md bg-muted p-3 text-sm leading-relaxed">
                  {doc.content}
                </p>
              </div>
            </div>
          ))}
          {documents.length === 0 && (
            <p className="text-sm text-muted-foreground">참조 문서가 없습니다.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
