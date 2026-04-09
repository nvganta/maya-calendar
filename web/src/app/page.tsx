"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // TODO: restore auth check before production
    router.replace("/dashboard");
  }, [router]);

  return null;
}
