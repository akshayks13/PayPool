import { ImageResponse } from "next/og";
import { logoDataUrl } from "@/lib/brand-image";

export const alt = "PayPool — independent shops, shared buying power.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "60px 90px",
        background: "linear-gradient(135deg, #ffffff, #eff6ff)",
        borderBottom: "18px solid #1d4ed8",
        color: "#0f172a",
      }}
    >
      <img src={await logoDataUrl()} alt="PayPool" width={660} height={220} />
      <div
        style={{
          display: "flex",
          fontSize: 48,
          fontWeight: 700,
          marginTop: 18,
        }}
      >
        Independent shops. Shared buying power.
      </div>
      <div
        style={{
          display: "flex",
          fontSize: 28,
          color: "#475569",
          marginTop: 24,
        }}
      >
        Buy together. Unlock wholesale prices. Share delivery costs.
      </div>
    </div>,
    size,
  );
}
