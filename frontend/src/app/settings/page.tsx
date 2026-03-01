"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Scissors,
  Binary,
  Search,
  ArrowUpDown,
  Sparkles,
  Shield,
  MessageSquare,
  FolderOpen,
} from "lucide-react";
import { cn } from "@/lib/utils";

const settingsCategories = [
  { href: "/settings/chunking", label: "청킹", desc: "문서 분할 전략 설정", icon: Scissors },
  { href: "/settings/embedding", label: "임베딩", desc: "임베딩 모델 및 프로바이더", icon: Binary },
  { href: "/settings/search", label: "검색", desc: "검색 모드 및 가중치", icon: Search },
  { href: "/settings/reranking", label: "리랭킹", desc: "리랭킹 모델 및 Top-K", icon: ArrowUpDown },
  { href: "/settings/hyde", label: "HyDE", desc: "가상 문서 생성 설정", icon: Sparkles },
  { href: "/settings/guardrails", label: "가드레일", desc: "PII, 인젝션, 할루시네이션 탐지", icon: Shield },
  { href: "/settings/generation", label: "답변 생성", desc: "LLM 모델 및 프롬프트", icon: MessageSquare },
  { href: "/settings/watcher", label: "디렉토리 감시", desc: "파일 자동 수집 설정", icon: FolderOpen },
];

export default function SettingsPage() {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">설정</h2>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
        {settingsCategories.map((cat) => {
          const Icon = cat.icon;
          const active = pathname === cat.href;
          return (
            <Link key={cat.href} href={cat.href}>
              <Card className={cn("cursor-pointer transition-colors hover:border-primary", active && "border-primary")}>
                <CardHeader className="flex flex-row items-center gap-3 pb-2">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <CardTitle className="text-sm">{cat.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs text-muted-foreground">{cat.desc}</p>
                </CardContent>
              </Card>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
