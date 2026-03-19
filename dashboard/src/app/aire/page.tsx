'use client';

import React, { useEffect, useRef } from 'react';

export default function AirePage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // This is a quick and dirty way to port the legacy HTML to Next.js 
    // without a full React rewrite. We'll use an iframe or just inject the HTML.
    // For a real refactor, this should be broken down into React components.
  }, []);

  return (
    <div className="w-full h-full bg-black">
      <iframe 
        src="/aire_map.html" 
        className="w-full h-full border-none"
        title="Zohar Air Quality Map"
      />
    </div>
  );
}
