import Link from "next/link";

const cards = [
  { href: "/materials", ico: "📚", title: "资料库", desc: "导入视频 / 音频 / YouTube / Bilibili" },
  { href: "/practice", ico: "✍️", title: "听写练习", desc: "听句子，填关键词" },
  { href: "/favorites", ico: "★", title: "收藏句子", desc: "你收藏的句子，随时复习" },
  { href: "/wrongbook", ico: "✗", title: "错题集", desc: "错满 3 次自动进错题集" },
];

export default function Home() {
  return (
    <div className="home">
      <div className="page-head">
        <div>
          <h1>🎧 ListenFlow</h1>
          <p className="subtitle">英语听力练习 · 听写填空</p>
        </div>
      </div>
      <div className="home-grid">
        {cards.map((c) => (
          <Link key={c.href} href={c.href} className="home-card">
            <div className="ico">{c.ico}</div>
            <h2>{c.title}</h2>
            <p>{c.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
