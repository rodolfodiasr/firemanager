import { useCallback, useEffect, useRef, useState } from "react";
import { operationsApi } from "../api/operations";

export type SpeechMode = "idle" | "recording" | "processing";

interface UseSpeechRecognitionReturn {
  mode: SpeechMode;
  transcript: string;
  supportsWebSpeech: boolean;
  start: () => void;
  stop: () => void;
  clear: () => void;
}

const supportsWebSpeech =
  typeof window !== "undefined" &&
  ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);

export function useSpeechRecognition(
  onTranscript: (text: string) => void
): UseSpeechRecognitionReturn {
  const [mode, setMode] = useState<SpeechMode>("idle");
  const [transcript, setTranscript] = useState("");

  // Web Speech API path
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // MediaRecorder path (Whisper fallback)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      mediaRecorderRef.current?.stop();
    };
  }, []);

  const startWebSpeech = useCallback(() => {
    const SpeechRecognitionCtor =
      (window as Window & { SpeechRecognition?: typeof SpeechRecognition; webkitSpeechRecognition?: typeof SpeechRecognition }).SpeechRecognition ||
      (window as Window & { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition;

    if (!SpeechRecognitionCtor) return false;

    const rec = new SpeechRecognitionCtor();
    rec.lang = "pt-BR";
    rec.interimResults = true;
    rec.continuous = false;

    rec.onresult = (e: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        if (result.isFinal) {
          final += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }
      const combined = final || interim;
      setTranscript(combined);
      if (final) {
        onTranscript(final);
        setMode("idle");
      }
    };

    rec.onerror = () => setMode("idle");
    rec.onend = () => setMode("idle");

    recognitionRef.current = rec;
    rec.start();
    setMode("recording");
    return true;
  }, [onTranscript]);

  const startWhisper = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setMode("processing");
        try {
          const blob = new Blob(chunksRef.current, { type: "audio/webm" });
          const result = await operationsApi.transcribe(blob);
          setTranscript(result.text);
          onTranscript(result.text);
        } catch {
          // silently fail — user can type instead
        } finally {
          setMode("idle");
        }
      };

      mediaRecorderRef.current = recorder;
      recorder.start();
      setMode("recording");
    } catch {
      setMode("idle");
    }
  }, [onTranscript]);

  const start = useCallback(() => {
    if (mode !== "idle") return;
    if (supportsWebSpeech) {
      startWebSpeech();
    } else {
      startWhisper();
    }
  }, [mode, startWebSpeech, startWhisper]);

  const stop = useCallback(() => {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const clear = useCallback(() => {
    setTranscript("");
  }, []);

  return { mode, transcript, supportsWebSpeech, start, stop, clear };
}
