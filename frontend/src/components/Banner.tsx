type BannerTone = "error" | "warning" | "success";

interface BannerProps {
  tone: BannerTone;
  title: string;
  body?: string;
}

export function Banner({ tone, title, body }: BannerProps) {
  return (
    <div className={`banner banner--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <p className="banner__title">{title}</p>
      {body ? <p className="banner__body">{body}</p> : null}
    </div>
  );
}
