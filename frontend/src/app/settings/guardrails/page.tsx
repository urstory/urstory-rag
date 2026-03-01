"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { GuardrailsForm } from "@/components/settings/guardrails-form";

export default function GuardrailsSettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/settings">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">가드레일 설정</h2>
      </div>
      <GuardrailsForm />
    </div>
  );
}
