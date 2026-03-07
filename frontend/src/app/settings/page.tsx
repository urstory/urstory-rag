"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
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
  UserCog,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const ragCategories = [
  { href: "/settings/chunking", label: "청킹", desc: "문서 분할 전략 설정", icon: Scissors },
  { href: "/settings/embedding", label: "임베딩", desc: "임베딩 모델 및 프로바이더", icon: Binary },
  { href: "/settings/search", label: "검색", desc: "검색 모드 및 가중치", icon: Search },
  { href: "/settings/reranking", label: "리랭킹", desc: "리랭킹 모델 및 Top-K", icon: ArrowUpDown },
  { href: "/settings/hyde", label: "HyDE", desc: "가상 문서 생성 설정", icon: Sparkles },
  { href: "/settings/guardrails", label: "가드레일", desc: "PII, 인젝션, 할루시네이션 탐지", icon: Shield },
  { href: "/settings/generation", label: "답변 생성", desc: "LLM 모델 및 프롬프트", icon: MessageSquare },
  { href: "/settings/watcher", label: "디렉토리 감시", desc: "파일 자동 수집 설정", icon: FolderOpen },
];

const accountCategories = [
  { href: "/settings/profile", label: "프로필", desc: "이름·비밀번호 변경", icon: UserCog },
  { href: "/settings/users", label: "사용자 관리", desc: "계정 생성·역할·비활성화", icon: Users, adminOnly: true },
];

export default function SettingsPage() {
  const pathname = usePathname();
  const { user } = useAuth();

  const visibleAccountCategories = accountCategories.filter(
    (cat) => !cat.adminOnly || user?.role === "admin",
  );

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">설정</h2>

      {/* 계정 관리 */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">계정</h3>
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {visibleAccountCategories.map((cat) => {
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

      {/* RAG 설정 */}
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">RAG 파이프라인</h3>
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {ragCategories.map((cat) => {
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
    </div>
  );
}
