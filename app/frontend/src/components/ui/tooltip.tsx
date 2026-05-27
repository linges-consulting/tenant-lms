import * as React from "react"
import { cn } from "@/lib/utils"

const TooltipProvider = ({ children }: { children: React.ReactNode }) => <>{children}</>

const Tooltip = ({ children }: { children: React.ReactNode }) => (
  <div className="relative inline-flex group">{children}</div>
)

const TooltipTrigger = ({ children }: { children: React.ReactNode; asChild?: boolean }) => (
  <>{children}</>
)

const TooltipContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
  <div
    ref={ref}
    className={cn(
      "absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-max max-w-xs rounded-md",
      "bg-popover border px-3 py-1.5 text-xs text-popover-foreground shadow-md",
      "invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity duration-150 pointer-events-none",
      className
    )}
    {...props}
  >
    {children}
  </div>
))
TooltipContent.displayName = "TooltipContent"

export { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger }
