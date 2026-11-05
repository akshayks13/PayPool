import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_right,_#dbeafe,_#f8fbff_55%)] px-6 py-10">
      <div className="mx-auto max-w-6xl">
        <nav className="flex items-center justify-between"><span className="text-xl font-black text-moss">paypool</span><Link className="btn-secondary" href="/login">Sign in</Link></nav>
        <section className="grid min-h-[70vh] items-center gap-12 py-16 lg:grid-cols-[1.2fr_0.8fr]">
          <div><p className="mb-4 font-semibold text-blue-700">Collective buying, clearly governed.</p><h1 className="max-w-3xl text-5xl font-black leading-tight tracking-tight text-ink md:text-6xl">Make every wholesale order work harder.</h1><p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">PayPool helps independent retailers pool demand, compare transparent landed costs, and explicitly approve every final order.</p><div className="mt-8 flex flex-wrap gap-3"><Link className="btn-primary" href="/login">Enter PayPool</Link><a className="btn-secondary" href="#how-it-works">How it works</a></div></div>
          <div className="card space-y-4 bg-ink text-white"><p className="text-sm font-semibold text-blue-200">THE PAYPOOL PROMISE</p><p className="text-2xl font-bold leading-relaxed">“No allocation clears above your agreed landed-cost ceiling.”</p><div className="grid grid-cols-3 gap-3 pt-4 text-center text-sm"><div><b className="block text-xl">1</b>Request</div><div><b className="block text-xl">2</b>Pool</div><div><b className="block text-xl">3</b>Approve</div></div></div>
        </section>
        <section id="how-it-works" className="grid gap-4 pb-12 md:grid-cols-3"><div className="card"><b>Structured requests</b><p className="mt-2 text-sm text-slate-600">Confirm what the agent extracted before it becomes a procurement request.</p></div><div className="card"><b>Transparent pooling</b><p className="mt-2 text-sm text-slate-600">See estimates clearly separated from locked allocation values.</p></div><div className="card"><b>Explicit approval</b><p className="mt-2 text-sm text-slate-600">Payments and orders only begin after backend-confirmed approval.</p></div></section>
      </div>
    </main>
  );
}
