import Link from "next/link";
import { Home, FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <FileQuestion className="h-12 w-12 text-muted-foreground" aria-hidden="true" />
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">페이지를 찾을 수 없습니다</h2>
        <p className="text-sm text-muted-foreground">
          요청하신 주소의 페이지가 존재하지 않거나 이동되었습니다.
        </p>
      </div>
      <Button asChild>
        <Link href="/">
          <Home className="mr-2 h-4 w-4" aria-hidden="true" />
          대시보드로
        </Link>
      </Button>
    </div>
  );
}
