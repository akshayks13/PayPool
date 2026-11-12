import Image from "next/image";

export function Brand({ onDark = false }: { onDark?: boolean }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center ${onDark ? "rounded-xl bg-white px-3 py-1" : ""}`}
    >
      <Image
        src="/paypool-logo.png"
        alt="PayPool"
        width={2172}
        height={724}
        sizes="(min-width: 1024px) 156px, 144px"
        priority
        className={onDark ? "h-10 w-auto" : "h-12 w-auto"}
      />
    </span>
  );
}
