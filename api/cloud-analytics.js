import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;
const supabase = createClient(supabaseUrl, supabaseKey);

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  
  try {
    const { data: projects, error } = await supabase
      .from('proyectos')
      .select('estado, promovente');

    if (error) throw error;

    const total = projects.length;
    
    const stateCounts = {};
    const promCounts = {};
    
    projects.forEach(p => {
      const st = (p.estado || 'DESCONOCIDO').toUpperCase().trim();
      const pr = (p.promovente || 'DESCONOCIDO').toUpperCase().trim();
      stateCounts[st] = (stateCounts[st] || 0) + 1;
      promCounts[pr] = (promCounts[pr] || 0) + 1;
    });

    const topStates = Object.entries(stateCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([k, v]) => [k.charAt(0) + k.slice(1).toLowerCase(), v]);

    const topPromoters = Object.entries(promCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([k, v]) => [k.charAt(0) + k.slice(1).toLowerCase(), v]);

    res.status(200).json({
      total,
      top_states: topStates,
      top_promoters: topPromoters,
      mode: 'cloud'
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
}
