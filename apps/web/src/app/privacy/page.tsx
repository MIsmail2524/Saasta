export const metadata = { title: "Privacy" };

export default function Privacy() {
  return (
    <article className="mx-auto max-w-3xl space-y-4 px-4 py-12 text-[15px] leading-7">
      <h1 className="text-3xl font-extrabold">Privacy</h1>
      <p className="text-muted">Short version: we use your photo to find products, then we forget it.</p>
      <h2 className="text-xl font-bold">Photos and videos you search with</h2>
      <ul className="list-disc space-y-1 pl-6">
        <li>Uploads are re-encoded on arrival, which strips location (GPS), camera and other hidden metadata.</li>
        <li>Anonymous search images are deleted after 72 hours. Logged-in users can clear their history at any time.</li>
        <li>Matching runs on Saasta&apos;s own models and servers. Your photos are never sent to third-party AI or search services.</li>
        <li>Videos are cut into a few still frames on our server. The original video is not kept.</li>
      </ul>
      <h2 className="text-xl font-bold">Try-on photos</h2>
      <p>Your try-on photo is processed in memory on our own servers and never written to storage. The generated result is saved to your account so you can view it, and is deleted with your account.</p>
      <h2 className="text-xl font-bold">Our crawler</h2>
      <p>SaastaBot indexes public product pages (title, price, link and a numeric image fingerprint). It obeys robots.txt, and stores can opt out at any time. See <a className="underline" href="/bot">saasta.pk/bot</a>.</p>
      <h2 className="text-xl font-bold">Model training</h2>
      <p>We only train our models on photos from stores that explicitly opted in. Shopper uploads and try-on photos are never used for training.</p>
      <h2 className="text-xl font-bold">Accounts</h2>
      <p>We store your email, a strongly hashed password (Argon2id), your watches and boards. You can delete your account from the account page, which removes all of it.</p>
      <h2 className="text-xl font-bold">Analytics for stores</h2>
      <p>Stores see only aggregate, anonymous demand data. A search query is never shown to a store unless at least 3 different searches match it. IP addresses are stored only as salted one-way hashes, for abuse prevention.</p>
      <h2 className="text-xl font-bold">Cookies</h2>
      <p>One essential, HttpOnly login cookie. No advertising trackers.</p>
    </article>
  );
}
