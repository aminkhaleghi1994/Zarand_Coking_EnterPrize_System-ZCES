import { redirect } from "next/navigation";

import { PageTransition } from "@/components/common/PageTransition";
import { AppChrome } from "@/components/layout/AppChrome";
import { getSession } from "@/lib/session";

export default async function AppLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const session = await getSession();
  if (!session.ok) {
    redirect(`/api/auth/refresh?next=/${locale}`);
  }

  return (
    <AppChrome identity={{ email: session.session.user.email, roles: session.session.roles }}>
      <PageTransition>{children}</PageTransition>
    </AppChrome>
  );
}
