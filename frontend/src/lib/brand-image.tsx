import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

export async function logoDataUrl() {
  const logo = await readFile(join(process.cwd(), "public/paypool-logo.png"));
  return `data:image/png;base64,${logo.toString("base64")}`;
}

export async function brandIcon(size: number) {
  // Display the existing monogram in a square viewport. Keep the original
  // artwork intact and omit the wordmark, which is unreadable at tab size.
  return new ImageResponse(
    <div
      style={{
        width: size,
        height: size,
        display: "flex",
        position: "relative",
        overflow: "hidden",
        background: "white",
        borderRadius: size / 5,
      }}
    >
      <img
        src={await logoDataUrl()}
        alt=""
        width={size * (2172 / 624)}
        height={size * (724 / 624)}
        style={{
          position: "absolute",
          left: -size * (48 / 624),
          top: -size * (48 / 624),
        }}
      />
    </div>,
    { width: size, height: size },
  );
}
