"use client";

import { DocumentList } from "@/components/documents/document-list";
import { DocumentUpload } from "@/components/documents/document-upload";

export default function DocumentsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">문서 관리</h2>
        <DocumentUpload />
      </div>
      <DocumentList />
    </div>
  );
}
