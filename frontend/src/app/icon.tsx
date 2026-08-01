import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: 8,
          background: "linear-gradient(145deg, #14141F 0%, #0B0B12 100%)",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <svg
          width="22"
          height="22"
          viewBox="0 0 22 22"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M2 11.5h1.1c.35 0 .6-.18.7-.5l.95-3.5c.2-.75 1.25-.75 1.45 0l1.35 5.2c.2.75 1.25.75 1.45 0l1.15-4.5c.2-.75 1.25-.75 1.45 0l.95 3.5c.1.32.35.5.7.5H20"
            stroke="url(#g)"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="19.2" cy="11.5" r="1.2" fill="#38BDF8" />
          <defs>
            <linearGradient id="g" x1="2" y1="11" x2="20" y2="11">
              <stop stopColor="#7DD3FC" />
              <stop offset="0.55" stopColor="#38BDF8" />
              <stop offset="1" stopColor="#A5B4FC" />
            </linearGradient>
          </defs>
        </svg>
      </div>
    ),
    { ...size },
  );
}
