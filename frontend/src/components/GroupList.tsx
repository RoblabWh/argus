// src/components/GroupList.tsx
import { useGroups } from "../hooks/goupHooks";

export function GroupList({ onSelect }: { onSelect: (id: number) => void }) {
  const { data: groups, isLoading, error } = useGroups();

  if (isLoading) return <p>Loading...</p>;
  if (error) return <p>Error loading groups</p>;

  return (
    <ul className="space-y-2">
      {groups?.map(group => (
        <li key={group.id} onClick={() => onSelect(group.id)} className="cursor-pointer hover:underline">
          {group.name}
        </li>
      ))}
    </ul>
  );
}
