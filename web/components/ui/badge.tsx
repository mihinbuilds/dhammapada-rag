import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border font-sans font-semibold uppercase tracking-wide whitespace-nowrap",
  {
    variants: {
      size: {
        sm: "px-2 py-0.5 text-[0.6rem] gap-1",
        md: "px-2.5 py-1 text-[0.66rem] gap-1.5",
      },
    },
    defaultVariants: { size: "sm" },
  },
);

function Badge({
  className,
  size,
  style,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return (
    <span
      className={cn(badgeVariants({ size, className }))}
      style={style}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
