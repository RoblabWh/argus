import React, { useState } from 'react';
import { GroupList } from '@/components/GroupList';

export default function Overview(){

  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);

  return (
    <div>
      <h1>Overview</h1>
      <p>This is the overview page.</p>
      <GroupList onSelect={(id) => setSelectedGroupId(id)} />
    </div>
  )
}
