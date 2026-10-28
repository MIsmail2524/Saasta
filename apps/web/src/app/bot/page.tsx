export const metadata = { title: "SaastaBot", description: "How Saasta's crawler works and how to opt out." };

export default function Bot() {
  return (
    <article className="mx-auto max-w-3xl space-y-4 px-4 py-12 text-[15px] leading-7">
      <h1 className="text-3xl font-extrabold">SaastaBot</h1>
      <p>
        SaastaBot builds Saasta&apos;s product index so shoppers can find where a product is sold. It identifies itself as{" "}
        <code className="rounded bg-surface px-1">SaastaBot/1.0 (+https://saasta.pk/bot)</code>.
      </p>
      <h2 className="text-xl font-bold">What it does</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>Reads only public product pages: via your sitemap, your public Shopify product feed, or structured product data (schema.org).</li>
        <li>Stores the product title, price, availability, link and a numeric image fingerprint. It never re-hosts your images, and every result links shoppers to your site.</li>
        <li>Obeys robots.txt (including Crawl-delay), makes at most one request per second, and revisits about once a week.</li>
      </ul>
      <h2 className="text-xl font-bold">Opt out</h2>
      <p>Add this to your robots.txt and we&apos;ll remove your products on the next visit:</p>
      <pre className="rounded-xl bg-ink p-4 text-sm text-bg">{`User-agent: SaastaBot
Disallow: /`}</pre>
      <p>
        Or email <a className="underline" href="mailto:bot@saasta.pk">bot@saasta.pk</a>. Want more control instead? <a className="underline" href="/stores">List your store as a partner</a>{" "}
        and manage your own catalog.
      </p>
    </article>
  );
}
