"use client";

import { LogOut, Menu, User, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useSystemStatus } from "@/lib/queries";
import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface HeaderProps {
  onMenuToggle: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
  const { data: systemStatus } = useSystemStatus();
  const { user, logout } = useAuth();
  const router = useRouter();

  const statusColor = !systemStatus
    ? "bg-gray-400"
    : systemStatus.status === "ok"
      ? "bg-green-500"
      : systemStatus.status === "degraded"
        ? "bg-yellow-500"
        : "bg-red-500";

  const statusLabel = !systemStatus
    ? "확인 중"
    : systemStatus.status === "ok"
      ? "정상"
      : systemStatus.status === "degraded"
        ? "일부 장애"
        : "장애";

  const handleLogout = async () => {
    await logout();
    router.push("/login");
  };

  return (
    <header className="flex h-14 items-center justify-between border-b px-4">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onMenuToggle}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <span className="text-sm font-medium md:hidden">UrstoryRAG</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">시스템 상태</span>
          <Badge variant="outline" className="gap-1.5">
            <span className={`h-2 w-2 rounded-full ${statusColor}`} />
            {statusLabel}
          </Badge>
        </div>
        {user && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="gap-2">
                <User className="h-4 w-4" />
                <span className="text-xs">
                  {user.name}
                </span>
                {user.role === "admin" && (
                  <Badge variant="secondary" className="text-[10px]">admin</Badge>
                )}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <div className="px-2 py-1.5">
                <p className="text-sm font-medium">{user.name}</p>
                <p className="text-xs text-muted-foreground">@{user.username}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem asChild>
                <Link href="/settings/profile" className="cursor-pointer">
                  <Settings className="mr-2 h-4 w-4" />
                  프로필 설정
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive">
                <LogOut className="mr-2 h-4 w-4" />
                로그아웃
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </header>
  );
}
