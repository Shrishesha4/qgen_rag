import { ScrollViewStyleReset } from 'expo-router/html';
import { type PropsWithChildren } from 'react';

/**
 * Customises the static HTML shell for the web export.
 * Sets the browser tab title and favicon to the QGen branding.
 */
export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, shrink-to-fit=no"
        />
        <meta name="description" content="QGen – AI-powered question generation for educators" />
        <ScrollViewStyleReset />
      </head>
      <body>{children}</body>
    </html>
  );
}
