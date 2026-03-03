export default function Header() {
  return (
    <header className="flex items-center bg-background-dark border-b border-border-dark p-3 sticky top-0 z-20">
      <div className="flex items-center gap-2 flex-1">
        <span className="material-symbols-outlined text-primary" style={{ fontSize: 24 }}>
          smart_toy
        </span>
        <h1 className="text-sm font-bold tracking-tight">AI Recorder</h1>
      </div>
      <div className="flex items-center gap-2">
        <button className="flex items-center justify-center p-2 rounded-lg hover:bg-white/10 transition-colors">
          <span className="material-symbols-outlined text-slate-300 text-[20px]">settings</span>
        </button>
      </div>
    </header>
  );
}
