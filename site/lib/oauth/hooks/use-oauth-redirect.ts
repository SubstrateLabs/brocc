"use client";

import { useState, useEffect } from "react";

export function useOAuthRedirect(domain: string, account?: string | null) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/auth/url/${domain}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ account }),
    })
      .then((res) => res.json())
      .then((data) => {
        if (data.url) {
          window.location.href = data.url;
        } else {
          setError("No URL returned from server");
        }
      })
      .catch((err) => {
        setError(err.message);
      });
  }, [domain, account]);

  return { error };
}
