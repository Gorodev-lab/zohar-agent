'use client';

import TerminalLayout from '@/components/TerminalLayout';
import ProjectsTable from '@/components/ProjectsTable';

export default function Home() {
  return (
    <TerminalLayout>
      <ProjectsTable />
    </TerminalLayout>
  );
}
