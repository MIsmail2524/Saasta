import { Account } from "./account";

export const metadata = { title: "My account", robots: { index: false } };

export default function Page() {
  return <Account />;
}
