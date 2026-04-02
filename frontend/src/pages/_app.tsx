import type { AppProps } from "next/app";
import { useEffect } from "react";
import "@/styles/globals.css";

const INJECTED_SCRIPT_PATH_REGEX = /^https?:\/\/[^/]+\/[0-9a-f-]+$/i;

function isKnownInjectedScriptAddListenerError(event: ErrorEvent): boolean {
  const message = event.message ?? "";
  const filename = event.filename ?? "";

  const isAddListenerTypeError =
    message.includes("Cannot read properties of undefined") &&
    message.includes("addListener");

  return isAddListenerTypeError && INJECTED_SCRIPT_PATH_REGEX.test(filename);
}

export default function App({ Component, pageProps }: AppProps) {
  useEffect(() => {
    // Suppress a known browser-extension injected script error in dev.
    const handleGlobalError = (event: ErrorEvent) => {
      if (!isKnownInjectedScriptAddListenerError(event)) {
        return;
      }

      event.preventDefault();
      event.stopImmediatePropagation();
    };

    window.addEventListener("error", handleGlobalError, true);

    return () => {
      window.removeEventListener("error", handleGlobalError, true);
    };
  }, []);

  return <Component {...pageProps} />;
}
