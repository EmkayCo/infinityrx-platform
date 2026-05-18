// SP-2 Plan B: page wrapper with route param.
// Logic in @infinityrx/module-directories — DrugDetailPage.
import { DrugDetailPage } from "@infinityrx/module-directories";

export default async function Page({ params }: { params: Promise<{ ndc: string }> }) {
  const { ndc } = await params;
  return <DrugDetailPage ndc={ndc} />;
}
