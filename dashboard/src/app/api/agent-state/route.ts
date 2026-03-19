import { NextResponse } from 'next/server';
import { supabase } from '@/lib/supabase';
import { touchHeartbeat, PATHS } from '@/lib/system';
import fs from 'fs';

export async function GET() {
  touchHeartbeat();
  
  const isVercel = process.env.VERCEL === '1';

  if (isVercel) {
    try {
      const { data, error } = await supabase
        .from('agente_status')
        .select('*')
        .eq('id', 1)
        .single();
      
      if (data && !error) {
        return NextResponse.json({
          pdf: data.pdf,
          action: data.action,
          target: data.target,
          time: data.last_seen?.slice(-8) || ''
        });
      }
    } catch (err) {
      console.error("Agent state Supabase error:", err);
    }
  }

  // Local fallback
  if (fs.existsSync(PATHS.STATE_FILE)) {
    try {
      const content = fs.readFileSync(PATHS.STATE_FILE, 'utf8');
      return NextResponse.json(JSON.parse(content));
    } catch (err) {
      console.error("Agent state file error:", err);
    }
  }

  return NextResponse.json({
    pdf: "INACTIVO",
    action: "ESPERA",
    target: "NINGUNO"
  });
}
