"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main id="main-content" className="standalone-error"><h1>We couldn’t load this workspace.</h1><p>The service may be unavailable. Check that the API and database are running, then try again.</p><button onClick={reset}>Try again</button></main>;
}
