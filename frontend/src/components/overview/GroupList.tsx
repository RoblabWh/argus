import { Accordion } from "@/components/ui/accordion";
import { GroupCard } from "@/components/GroupCard";
import type { Group } from "@/types";


interface Props {
  groups: Group[];
}

export function GroupList({ groups }: Props) {
  return (
    <>
      {groups.map((group) => (
        <GroupCard key={group.id} group={group} />
      ))}
    </>
  );
  
}