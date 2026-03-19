import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';

interface RouteParams {
    params: Promise<{ id: string }>
}

export async function GET(req: Request, { params }: RouteParams) {
  const { id } = await params;
  
  try {
    const { data, error } = await supabase
      .from('proyectos')
      .select('*')
      .eq('id_proyecto', id)
      .single();
    
    if (error) {
      if (error.code === 'PGRST116') {
        return NextResponse.json({ error: "Proyecto no hallado" }, { status: 404 });
      }
      throw error;
    }

    return NextResponse.json(data);
  } catch (err: any) {
    console.error("Project detail error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
