export const metadata = { title: "Terms" };

export default function Terms() {
  return (
    <article className="mx-auto max-w-3xl space-y-4 px-4 py-12 text-[15px] leading-7">
      <h1 className="text-3xl font-extrabold">Terms of use</h1>
      <p>Saasta is a discovery tool. We show where products appear to be sold. We are not the seller and are not part of your purchase.</p>
      <ul className="list-disc space-y-1 pl-6">
        <li>Prices, stock and reviews come from third parties and can be wrong or out of date. Check on the seller&apos;s site before paying.</li>
        <li>Trust scores are automated signals, not guarantees. Use cash on delivery or buyer protection where possible.</li>
        <li>Only upload images you have the right to use. Don&apos;t upload images of other people for try-on without their permission.</li>
        <li>No scraping, automated querying or reselling of results without a written agreement.</li>
        <li>Stores may only list products they actually sell, on a domain they have verified.</li>
      </ul>
    </article>
  );
}
