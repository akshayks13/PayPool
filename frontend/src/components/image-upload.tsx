"use client";
import { useState } from "react";
import { request } from "@/lib/http";

export function ImageUpload({
  path,
  label,
  onUploaded,
}: {
  path: string;
  label: string;
  onUploaded: (image: { id: string; url: string }) => void;
}) {
  const [file, setFile] = useState<File | null>(null),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function upload() {
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) {
      setMessage("Choose an image up to 2 MB.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const data = new FormData();
      data.append("file", file);
      const image = await request<{ id: string; url: string }>(path, {
        method: "POST",
        body: data,
      });
      onUploaded(image);
      setMessage("Image uploaded. Embedded metadata was removed.");
      setFile(null);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Image upload failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="rounded-xl border p-4 md:col-span-2">
      <label className="label block">
        {label}
        <input
          className="field"
          type="file"
          aria-label={`Choose file for ${label.toLowerCase()}`}
          accept="image/png,image/jpeg,image/webp"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
            setMessage("");
          }}
          disabled={busy}
        />
      </label>
      <p className="mt-2 text-xs text-slate-500">
        PNG, JPEG or WebP · 2 MB maximum · photos are normalized to at most 2048
        px and stored privately.
      </p>
      <button
        className="btn-secondary mt-3"
        type="button"
        disabled={!file || busy}
        onClick={upload}
      >
        {busy ? "Uploading image…" : label}
      </button>
      {message && (
        <p role="status" className="mt-2 text-sm">
          {message}
        </p>
      )}
    </div>
  );
}
