import { useEffect } from 'react';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { ModeToggle } from '@/components/ui/mode-toggle';

export default function Settings() {
  const { setBreadcrumbs } = useBreadcrumbs();

  useEffect(() => {
    setBreadcrumbs([{ label: "Settings", href: "/settings" }]);
  }, [setBreadcrumbs]);

  return (
    <div className="container mx-auto px-4 pt-4">
        <h1 className="text-2xl font-bold mb-4 mr-2">Settings</h1>
        
        <p>This is the settings page.</p>
    </div>
  )
}
