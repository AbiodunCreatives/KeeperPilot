export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-center bg-zinc-50 font-sans dark:bg-black">
      <main className="flex flex-1 w-full max-w-3xl flex-col items-center justify-between py-32 px-16 bg-white dark:bg-black sm:items-start">
        <div className="flex flex-col items-center gap-6 text-center sm:items-start sm:text-left">
          <span className="rounded-full border border-zinc-200 px-3 py-1 text-xs font-medium text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
            KeeperPilot · execution by KeeperHub
          </span>
          <h1 className="max-w-lg text-4xl font-semibold leading-tight tracking-tight text-black dark:text-zinc-50">
            Your personal AI DeFi manager.
          </h1>
          <p className="max-w-md text-lg leading-8 text-zinc-600 dark:text-zinc-400">
            KeeperPilot watches your positions 24/7, finds risk-adjusted yield
            opportunities, and executes through KeeperHub — all within policies
            you define.
          </p>
        </div>
        <div className="flex flex-col gap-4 text-base font-medium sm:flex-row">
          <a
            className="flex h-12 w-full items-center justify-center rounded-full bg-zinc-900 px-6 text-zinc-50 transition-colors hover:bg-zinc-700 dark:bg-zinc-50 dark:text-black dark:hover:bg-zinc-300"
            href="/api/health"
          >
            Check backend health
          </a>
          <a
            className="flex h-12 w-full items-center justify-center rounded-full border border-solid border-black/[.08] px-6 transition-colors hover:border-transparent hover:bg-black/[.04] dark:border-white/[.145] dark:hover:bg-[#1a1a1a]"
            href="https://docs.keeperhub.com/quickstart"
            target="_blank"
            rel="noopener noreferrer"
          >
            KeeperHub docs
          </a>
        </div>
      </main>
    </div>
  );
}
