import { useEffect } from 'react';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';

export default function About(){
  const { setBreadcrumbs } = useBreadcrumbs();
  useEffect(() => {
    setBreadcrumbs([{ label: "About", href: "/about" }]);
  }, [setBreadcrumbs]);

  return (
    <div className="p-6 mx-auto min-w-800px max-w-2/3">
      <h1 className="text-2xl font-bold mb-4 mr-2">About</h1>
      <p>This is the about page.</p>
    </div>
  )
}
