const { createClient } = require('@supabase/supabase-js');

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

export default async function handler(req, res) {
  // Manejo de CORS para el Dashboard
  res.setHeader('Access-Control-Allow-Credentials', true);
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,OPTIONS,PATCH,DELETE,POST,PUT');
  res.setHeader('Access-Control-Allow-Headers', 'X-CSRF-Token, X-Requested-With, Accept, Accept-Version, Content-Length, Content-MD5, Content-Type, Date, X-Api-Version, bypass-tunnel-reminder');

  if (req.method === 'OPTIONS') {
    res.status(200).end();
    return;
  }

  try {
    const { data, error } = await supabase
      .from('proyectos')
      .select('*')
      .order('updated_at', { ascending: false });

    const normalized = data.map(r => ({
      ID_PROYECTO: r.id_proyecto,
      ANIO: r.anio,
      ESTADO: r.estado,
      MUNICIPIO: r.municipio,
      LOCALIDAD: r.localidad,
      PROYECTO: r.proyecto,
      PROMOVENTE: r.promovente,
      SECTOR: r.sector,
      INSIGHT: r.insight,
      FUENTES: r.fuentes_web,
      audit_status: 'cloud'
    }));

    res.status(200).json(normalized);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}
