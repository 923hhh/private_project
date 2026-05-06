import { Suspense } from "react";

import KnowledgeListPage from "@/features/knowledge/screens/knowledge-list-page";

export default function KnowledgePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <KnowledgeListPage />
    </Suspense>
  );
}
