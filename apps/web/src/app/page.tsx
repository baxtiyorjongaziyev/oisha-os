import { Button } from "@salescoach/ui";

const capabilities = [
  "Qo'ng'iroqlarni yuklash va navbatga qo'yish",
  "Whisper va diarization uchun worker poydevori",
  "Rubrika asosida AI skoringga tayyor arxitektura",
  "Xavfsiz share-link oqimi uchun alohida modul reja"
];

export default function HomePage() {
  return (
    <main id="main-content" className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-6 py-16 focus:outline-none" tabIndex={-1}>
      <section className="rounded-[2rem] border border-sage/15 bg-white/80 p-8 shadow-2xl shadow-sage/10 backdrop-blur md:p-12">
        <p className="mb-4 text-sm font-semibold uppercase tracking-[0.35em] text-amberline">
          Oisha OS platform layer
        </p>
        <h1 className="max-w-3xl font-display text-5xl leading-tight text-ink md:text-7xl">
          SalesCoach AI sotuv qo&apos;ng&apos;iroqlarini sifat nazoratiga aylantiradi.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-ink/70">
          Bu sahifa MVP poydevori: real audio pipeline, CRM ingestion, AI scoring va Telegram
          coaching keyingi bosqichlarda shu monorepo ichida ulanadi.
        </p>
        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Button>Dashboard poydevori tayyor</Button>
          <Button variant="secondary">API: /healthz</Button>
        </div>
      </section>

      <ul aria-label="Platformaning imkoniyatlari" className="mt-8 grid gap-4 md:grid-cols-2">
        {capabilities.map((item) => (
          <li key={item} className="rounded-3xl border border-sage/10 bg-white/70 p-5 text-ink/75">
            {item}
          </li>
        ))}
      </ul>
    </main>
  );
}
