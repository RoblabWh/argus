import { useEffect } from 'react';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';

export default function About(){
  const { setBreadcrumbs } = useBreadcrumbs();
  useEffect(() => {
    setBreadcrumbs([{ label: "About", href: "/about" }]);
  }, [setBreadcrumbs]);

  return (
    <div className="container mx-auto px-4 pt-4">
      <h1 className="text-2xl font-bold mb-4 mr-2">About</h1>
      <p>This is the about page.</p>
    </div>
  )
}
