import { PageTransition } from "@/components/PageTransition";

/** Remounts on every navigation — drives enter animations in PageTransition. */
export default function Template({ children }: { children: React.ReactNode }) {
  return <PageTransition>{children}</PageTransition>;
}
