// components/ResponsiveResizableLayout.tsx
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useAspectRatio } from "@/hooks/useAspectRatio";

export function ResponsiveResizableLayout({
  left,
  right,
}: {
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  const isPortrait = useAspectRatio();

  if (isPortrait) {
    return (
    <ResizablePanelGroup direction="vertical" className="w-screen h-screen">
      <ResizablePanel defaultSize={33} minSize={20}>
        <div className="h-full w-full overflow-auto p-4">{left}</div>
      </ResizablePanel>
      <ResizableHandle className="cursor-col-resize" withHandle={true} />
      <ResizablePanel defaultSize={67} minSize={20}>
        <div className="h-full w-full overflow-auto p-4">{right}</div>
      </ResizablePanel>
    </ResizablePanelGroup>
    );
  }

  return (
    <ResizablePanelGroup direction="horizontal" className="w-screen h-screen">
      <ResizablePanel defaultSize={26} minSize={10}>
        <div className="h-full w-full overflow-auto p-2 pr-4">{left}</div>
      </ResizablePanel>
      <ResizableHandle className=" cursor-col-resize" withHandle={true} />
      <ResizablePanel defaultSize={74} minSize={10} className=" h-[calc(100vh-54px)]">
        <div className="h-full w-full p-2 pl-4">{right}</div>
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
