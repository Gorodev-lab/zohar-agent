import { redirect } from 'next/navigation';

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  
  // SEMARNAT GIS Viewer pattern for 2026 files
  const externalUrl = `https://gisviewer.semarnat.gob.mx/gacetas/archivos2026/${id}.pdf`;
  
  redirect(externalUrl);
}
