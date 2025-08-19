import { useState } from 'react';
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from "lucide-react";
import type { Report } from '@/types/report';
import { EditGroupPopup } from './EditGroupPopup';
import type { Group } from '@/types';

interface Props {
    group: Group;
}

export function GeneralDataCard({ group }: Props) {
    const [editPopupOpen, setEditPopupOpen] = useState(false);

    const onEditDetailsClick = () => {
        setEditPopupOpen(true);
    };

    return (
        <>
            <Card className="min-w-80 max-w-480 w-full flex-3 px-4 py-3">
                <CardContent className="px-0 py-2 flex flex-col justify-between h-full">
                    {/* Title */}
                    <div className="flex justify-between items-start w-full">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="text-2xl font-bold leading-nonetruncate max-w-[28rem]">
                                    {group.name}
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>{group.name}</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>

                    {/* Description */}
                    <div className="flex items-center justify-start w-full gap-1 mt-0">
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <div className="text-sm text-muted-foreground line-clamp-3 max-w-[28rem]">
                                    {group.description || "No description available"}
                                </div>
                            </TooltipTrigger>
                            <TooltipContent>
                                <p>{group.description || "No description available"}</p>
                            </TooltipContent>
                        </Tooltip>
                    </div>

                    <div className="flex-1" />

                    {/* Bottom section */}
                    <div className="flex flex-row items-end justify-between mt-4">
                        <div className="w-full">

                            <p className="text-sm text-muted-foreground">
                                Created: {new Date(group.created_at).toLocaleDateString()} at{" "}
                                {new Date(group.created_at).toLocaleTimeString()}
                            </p>
                            <p className="text-[10px] text-muted-foreground mt-0">
                                ID: {group.id}
                            </p>

                        </div>

                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button variant="ghost" size="icon" className="ml-2">
                                    <MoreHorizontal className="w-5 h-5" />
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                                <DropdownMenuItem onClick={onEditDetailsClick}> Edit details</DropdownMenuItem>
                                <DropdownMenuItem className="text-red-600">Delete</DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>

                    </div>
                </CardContent>
            </Card>
            <EditGroupPopup
                open={editPopupOpen}
                onOpenChange={setEditPopupOpen}
                groupId={group.id}
                initialName={group.name}
                initialDescription={group.description}
            />
        </>
    );
}
