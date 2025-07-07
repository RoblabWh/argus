import { use, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useBreadcrumbs } from '@/contexts/BreadcrumbContext';
import { useGroup } from '@/hooks/groupHooks';

export default function Group() {
    const { id } = useParams<{ id: string }>();
    const { setBreadcrumbs } = useBreadcrumbs();
    const { data: group, isLoading, error } = useGroup(Number(id));

    useEffect(() => {
        setBreadcrumbs([
            { label: "Overview", href: "/overview" },
            { label: "Group", href: `/group/${id}` }]);
    }, []);

    useEffect(() => {
        if (group) {
            setBreadcrumbs([
                { label: "Overview", href: "/overview" },
                { label: group.name, href: `/group/${group.id}` },
            ]);
        }
    }, [group]);

    if (isLoading) return <div>Loading...</div>;
    if (error) return <div>Error loading group</div>;
    if (!group) return <div>Group not found</div>;



    return (
        <div className="container mx-auto px-4 pt-4">
            <h1 className="text-2xl font-bold mb-4 mr-2">Group: {group.name}</h1>

            <p>This is the group page.</p>
            
            <div className="text-sm text-muted-foreground mt-4">
                <pre>{JSON.stringify(group, null, 2)}</pre>
            </div>
        </div>
    )
}
