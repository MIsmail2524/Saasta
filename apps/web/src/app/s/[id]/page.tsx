import type { Metadata } from "next";
import { Results } from "./results";

export const metadata: Metadata = { title: "Results", robots: { index: false } };

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Results id={id} />;
}
