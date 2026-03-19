import { NextResponse } from 'next/server';
import { PATHS } from '@/lib/system';
import { promises as fsp } from 'fs';
import fs from 'fs';

export async function GET() {
  if (!fs.existsSync(PATHS.LOG_FILE)) {
    return NextResponse.json([]);
  }

  try {
    const TAIL_BYTES = 8 * 1024;
    const stats = await fsp.stat(PATHS.LOG_FILE);
    const size = stats.size;
    const readSize = Math.min(size, TAIL_BYTES);
    const buffer = Buffer.alloc(readSize);
    
    // Non-blocking file read
    const fileHandle = await fsp.open(PATHS.LOG_FILE, 'r');
    await fileHandle.read(buffer, 0, readSize, Math.max(0, size - TAIL_BYTES));
    await fileHandle.close();
    
    const raw = buffer.toString('utf8');
    let lines = raw.split('\n');
    
    // Discard partial first line if we jumped into the file
    if (size > TAIL_BYTES) {
      lines = lines.slice(1);
    }
    
    const logs = [];
    for (let line of lines) {
      line = line.trim();
      if (!line) continue;
      
      try {
        const entry = JSON.parse(line);
        // Clean up emojis like Python code
        if (entry.msg && typeof entry.msg === 'string') {
          entry.msg = entry.msg.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{27BF}\u{FE00}-\u{FEFF}\u{2700}-\u{27BF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2702}-\u{27B0}\u{231A}-\u{231B}\u{23E9}-\u{23F3}\u{23F8}-\u{23FA}\u{25AA}-\u{25AB}\u{25B6}\u{25C0}\u{25FB}-\u{25FE}\u{2934}-\u{2935}\u{2B05}-\u{2B07}\u{2B1B}-\u{2B1C}\u{2B50}\u{2B55}\u{3030}\u{303D}\u{3297}\u{3299}\u{200D}\u{20E3}\u{FE0F}]/gu, '').trim();
          entry.msg = entry.msg.replace(/\s+/g, ' ');
        }
        logs.push(entry);
      } catch (err) {
        // Skip invalid lines
      }
    }
    
    return NextResponse.json(logs.slice(-50));
  } catch (err) {
    console.error("Log tailing error:", err);
    return NextResponse.json([]);
  }
}
