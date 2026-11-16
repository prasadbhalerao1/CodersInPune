"use client";

import { Mic, MicOff, Volume2 } from "lucide-react";
import { useEffect, useRef, useState, type TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

type Recognition = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  start: () => void;
  stop: () => void;
};

function recognition(): Recognition | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  };
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

/**
 * A textarea the leaver can talk into. Speech is turned into text by the browser itself
 * (nothing is recorded or uploaded by Relay); the person reads and edits it before saving.
 * `speak` reads the question aloud. Without browser support the buttons simply don't show.
 */
export function VoiceTextarea({
  speak,
  className,
  defaultValue,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { speak?: string }) {
  const [value, setValue] = useState(String(defaultValue ?? ""));
  const [listening, setListening] = useState(false);
  const [supported, setSupported] = useState({ listen: false, talk: false });
  const [error, setError] = useState<string | null>(null);
  const rec = useRef<Recognition | null>(null);

  useEffect(() => {
    // Feature detection must run in the browser, after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSupported({ listen: recognition() !== null, talk: "speechSynthesis" in window });
    return () => rec.current?.stop();
  }, []);

  function toggle() {
    if (listening) {
      rec.current?.stop();
      return;
    }
    const r = recognition();
    if (!r) return;
    r.continuous = true;
    r.interimResults = false;
    r.lang = navigator.language || "en-GB";
    r.onresult = (e) => {
      let said = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) said += e.results[i][0].transcript;
      }
      if (said) setValue((v) => (v ? `${v.trimEnd()} ${said.trim()}` : said.trim()));
    };
    r.onerror = (e) =>
      setError(e.error === "not-allowed" ? "Microphone access was blocked." : "Dictation stopped.");
    r.onend = () => setListening(false);
    rec.current = r;
    setError(null);
    setListening(true);
    r.start();
  }

  return (
    <div className="flex flex-col gap-1">
      <textarea
        {...props}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className={className}
      />
      {supported.listen || (supported.talk && speak) ? (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {supported.listen ? (
            <button
              type="button"
              onClick={toggle}
              aria-pressed={listening}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-1 transition-colors",
                listening
                  ? "border-red-500/50 bg-red-50 text-red-700 dark:bg-red-950/40 dark:text-red-300"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {listening ? (
                <>
                  <MicOff aria-hidden className="size-3.5" /> Stop dictating
                  <span className="copilot-pulse" aria-hidden />
                </>
              ) : (
                <>
                  <Mic aria-hidden className="size-3.5" /> Answer by voice
                </>
              )}
            </button>
          ) : null}
          {supported.talk && speak ? (
            <button
              type="button"
              onClick={() => {
                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(new SpeechSynthesisUtterance(speak));
              }}
              className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 rounded-md border px-2 py-1"
            >
              <Volume2 aria-hidden className="size-3.5" /> Read the question aloud
            </button>
          ) : null}
          {error ? <span role="alert" className="text-amber-700 dark:text-amber-300">{error}</span> : null}
          {listening ? (
            <span className="text-muted-foreground">Speech is turned into text by your browser.</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
