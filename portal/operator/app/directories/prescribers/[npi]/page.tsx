// SP-2 Plan B: page wrapper with route param.
// Logic in @infinityrx/module-directories — PrescriberDetailPage.
import { PrescriberDetailPage } from "@infinityrx/module-directories";

export default async function Page({ params }: { params: Promise<{ npi: string }> }) {
  const { npi } = await params;
  return <PrescriberDetailPage npi={npi} />;
}
