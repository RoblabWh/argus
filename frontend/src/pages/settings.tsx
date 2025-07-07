import { useEffect } from 'react';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';

export default function Settings() {
  const { setBreadcrumbs } = useBreadcrumbs();

  useEffect(() => {
    setBreadcrumbs([{ label: "Settings", href: "/settings" }]);
  }, [setBreadcrumbs]);

  return (
    <div className="p-6 mx-auto min-w-800px max-w-2/3">
        <h1 className="text-2xl font-bold mb-4 mr-2">Settings</h1>
        
        <p>This is the settings page.</p>
    </div>
  )
}
