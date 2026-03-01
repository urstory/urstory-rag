"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Database, Play, GitCompare } from "lucide-react";

const evalSections = [
  {
    href: "/evaluation/datasets",
    label: "데이터셋",
    desc: "평가용 QA 쌍 데이터셋 관리",
    icon: Database,
  },
  {
    href: "/evaluation/runs",
    label: "평가 실행",
    desc: "평가 실행 및 결과 확인",
    icon: Play,
  },
  {
    href: "/evaluation/compare",
    label: "비교",
    desc: "두 평가 실행 결과 비교",
    icon: GitCompare,
  },
];

export default function EvaluationPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">평가 (RAGAS)</h2>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
        {evalSections.map((section) => {
          const Icon = section.icon;
          return (
            <Link key={section.href} href={section.href}>
              <Card className="cursor-pointer transition-colors hover:border-primary">
                <CardHeader className="flex flex-row items-center gap-3 pb-2">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-sm">{section.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">{section.desc}</p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
