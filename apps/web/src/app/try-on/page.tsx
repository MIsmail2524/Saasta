import { Suspense } from "react";
import { TryOn } from "./try-on";

export const metadata = { title: "Virtual try-on" };

export default function Page() {
  return (
    <Suspense>
      <TryOn />
    </Suspense>
  );
}
