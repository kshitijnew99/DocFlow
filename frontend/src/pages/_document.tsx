import { Html, Head, Main, NextScript } from "next/document";

export default function Document() {
  const injectedScriptErrorGuard = `
    (function () {
      var injectedScriptPath = /^https?:\\/\\/[^/]+\\/[0-9a-f-]+(?:$|[:?#])/i;

      function isInjectedAddListenerError(message, filename) {
        var msg = message || "";
        var file = filename || "";
        return (
          msg.indexOf("Cannot read properties of undefined") !== -1 &&
          msg.indexOf("addListener") !== -1 &&
          injectedScriptPath.test(file)
        );
      }

      window.addEventListener(
        "error",
        function (event) {
          if (!event) return;

          if (!isInjectedAddListenerError(event.message, event.filename)) {
            return;
          }

          event.preventDefault();
          if (event.stopImmediatePropagation) {
            event.stopImmediatePropagation();
          }
        },
        true
      );

      window.addEventListener(
        "unhandledrejection",
        function (event) {
          if (!event) return;

          var reason = event.reason;
          var message = "";
          if (reason && typeof reason.message === "string") {
            message = reason.message;
          } else if (typeof reason === "string") {
            message = reason;
          }

          if (
            message.indexOf("Cannot read properties of undefined") === -1 ||
            message.indexOf("addListener") === -1
          ) {
            return;
          }

          event.preventDefault();
          if (event.stopImmediatePropagation) {
            event.stopImmediatePropagation();
          }
        },
        true
      );
    })();
  `;

  return (
    <Html lang="en">
      <Head>
        <script dangerouslySetInnerHTML={{ __html: injectedScriptErrorGuard }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,300&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
        <meta name="description" content="DocFlow — Async Document Processing System" />
      </Head>
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
