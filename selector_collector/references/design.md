<!DOCTYPE html>
<html class="dark" lang="en"><head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>AI Recorder with Smart Grouping</title>
<script src="https://cdn.tailwindcss.com?plugins=forms,container-queries"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&amp;display=swap" rel="stylesheet"/>
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>
<script id="tailwind-config">
        tailwind.config = {
            darkMode: "class",
            theme: {
                extend: {
                    colors: {
                        "primary": "#1919e6",
                        "background-light": "#f6f6f8",
                        "background-dark": "#0c0c16",
                        "panel-dark": "#16162a",
                        "border-dark": "#2d2d50",
                        "accent-green": "#0bda68"
                    },
                    fontFamily: {
                        "display": ["Inter", "sans-serif"]
                    },
                    borderRadius: {
                        "DEFAULT": "0.25rem",
                        "lg": "0.5rem",
                        "xl": "0.75rem",
                        "full": "9999px"
                    },
                },
            },
        }
    </script>
<style type="text/tailwindcss">
        body { font-family: 'Inter', sans-serif; }
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #343465; border-radius: 10px; }
        .step-group-header {
            @apply flex items-center gap-2 p-2 bg-slate-100 dark:bg-border-dark/30 rounded-lg cursor-pointer hover:bg-slate-200 dark:hover:bg-border-dark/50 transition-colors mb-1;
        }
    </style>
<style>
    body {
      min-height: max(884px, 100dvh);
    }
  </style>
  </head>
<body class="bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 min-h-screen flex flex-col overflow-hidden">
<header class="flex items-center bg-white dark:bg-background-dark border-b border-slate-200 dark:border-border-dark p-3 sticky top-0 z-20">
<div class="flex items-center gap-2 flex-1">
<span class="material-symbols-outlined text-primary" style="font-size: 24px;">smart_toy</span>
<h1 class="text-sm font-bold tracking-tight">AI Recorder</h1>
</div>
<div class="flex items-center gap-2">
<button class="flex items-center justify-center p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-white/10 transition-colors">
<span class="material-symbols-outlined text-slate-600 dark:text-slate-300 text-[20px]">settings</span>
</button>
</div>
</header>
<div class="flex items-center gap-2 p-3 bg-white dark:bg-background-dark border-b border-slate-200 dark:border-border-dark z-10">
<button class="flex items-center gap-1.5 bg-red-500 hover:bg-red-600 text-white px-3 py-1.5 rounded-full text-xs font-semibold transition-all shadow-sm">
<span class="material-symbols-outlined text-sm">fiber_manual_record</span>
        Record
    </button>
<button class="flex items-center gap-1.5 bg-primary hover:bg-blue-700 text-white px-3 py-1.5 rounded-full text-xs font-semibold transition-all shadow-sm">
<span class="material-symbols-outlined text-sm">play_arrow</span>
        Replay
    </button>
<div class="h-5 w-[1px] bg-slate-200 dark:bg-border-dark mx-1"></div>
<button class="flex items-center gap-1.5 text-slate-600 dark:text-slate-300 px-2 py-1.5 rounded-lg text-xs font-medium hover:bg-slate-100 dark:hover:bg-white/5">
<span class="material-symbols-outlined text-sm">api</span>
        LLM API
    </button>
</div>
<main class="flex-1 flex flex-col overflow-hidden">
<section class="flex-1 flex flex-col overflow-y-auto custom-scrollbar p-3">
<div class="flex items-center justify-between mb-4">
<h2 class="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Smart Step Grouping</h2>
<span class="text-[10px] bg-primary/10 text-primary px-2 py-0.5 rounded-full font-bold">2 Groups • 6 Steps</span>
</div>
<div class="space-y-4">
<div class="group-container">
<div class="step-group-header">
<span class="material-symbols-outlined text-slate-400 text-sm">expand_more</span>
<span class="material-symbols-outlined text-primary text-[18px]">lock_open</span>
<span class="text-xs font-bold flex-1">Login Flow</span>
<span class="text-[10px] text-slate-400 bg-slate-200 dark:bg-slate-800 px-1.5 rounded">3 steps</span>
</div>
<div class="pl-4 space-y-2 mt-2">
<div class="flex items-center gap-3 p-2 bg-white dark:bg-panel-dark border border-slate-200 dark:border-border-dark rounded-lg group">
<span class="material-symbols-outlined text-slate-400 text-[18px]">edit_note</span>
<div class="flex-1 min-w-0">
<input class="w-full bg-transparent border-none p-0 text-xs font-medium focus:ring-0 text-slate-800 dark:text-slate-200" type="text" value="Fill email"/>
<p class="text-[10px] text-slate-400 truncate">input[name="user_email"]</p>
</div>
<span class="material-symbols-outlined text-accent-green text-[16px]">check_circle</span>
</div>
<div class="flex items-center gap-3 p-2 bg-white dark:bg-panel-dark border border-slate-200 dark:border-border-dark rounded-lg">
<span class="material-symbols-outlined text-slate-400 text-[18px]">password</span>
<div class="flex-1 min-w-0">
<input class="w-full bg-transparent border-none p-0 text-xs font-medium focus:ring-0 text-slate-800 dark:text-slate-200" type="text" value="Enter password"/>
<p class="text-[10px] text-slate-400 truncate">input#pass-field</p>
</div>
<span class="material-symbols-outlined text-accent-green text-[16px]">check_circle</span>
</div>
<div class="flex items-center gap-3 p-2 bg-white dark:bg-panel-dark border border-slate-200 dark:border-border-dark rounded-lg">
<span class="material-symbols-outlined text-slate-400 text-[18px]">login</span>
<div class="flex-1 min-w-0">
<input class="w-full bg-transparent border-none p-0 text-xs font-medium focus:ring-0 text-slate-800 dark:text-slate-200" type="text" value="Click Sign In"/>
<p class="text-[10px] text-slate-400 truncate">button.auth-submit</p>
</div>
<span class="material-symbols-outlined text-accent-green text-[16px]">check_circle</span>
</div>
</div>
</div>
<div class="group-container">
<div class="step-group-header">
<span class="material-symbols-outlined text-slate-400 text-sm">expand_more</span>
<span class="material-symbols-outlined text-primary text-[18px]">search</span>
<span class="text-xs font-bold flex-1">Search Process</span>
<span class="text-[10px] text-slate-400 bg-slate-200 dark:bg-slate-800 px-1.5 rounded">3 steps</span>
</div>
<div class="pl-4 space-y-2 mt-2">
<div class="flex items-center gap-3 p-2 bg-white dark:bg-panel-dark border border-slate-200 dark:border-border-dark rounded-lg">
<span class="material-symbols-outlined text-slate-400 text-[18px]">search_check</span>
<div class="flex-1 min-w-0">
<input class="w-full bg-transparent border-none p-0 text-xs font-medium focus:ring-0 text-slate-800 dark:text-slate-200" type="text" value="Focus search bar"/>
<p class="text-[10px] text-slate-400 truncate">div.search-input-container</p>
</div>
<span class="material-symbols-outlined text-accent-green text-[16px]">check_circle</span>
</div>
<div class="flex items-center gap-3 p-2 bg-white dark:bg-panel-dark border border-slate-200 dark:border-border-dark rounded-lg">
<span class="material-symbols-outlined text-slate-400 text-[18px]">keyboard</span>
<div class="flex-1 min-w-0">
<input class="w-full bg-transparent border-none p-0 text-xs font-medium focus:ring-0 text-slate-800 dark:text-slate-200" type="text" value="Type 'Automation'"/>
<p class="text-[10px] text-slate-400 truncate">input#global-search</p>
</div>
<span class="material-symbols-outlined text-accent-green text-[16px]">check_circle</span>
</div>
<div class="flex items-center gap-3 p-2 bg-primary/5 border border-primary/20 rounded-lg">
<span class="material-symbols-outlined text-primary text-[18px]">pending</span>
<div class="flex-1 min-w-0">
<p class="text-xs font-medium text-primary">Inferred Intent...</p>
<p class="text-[10px] text-primary/70 truncate">Press Enter key</p>
</div>
<div class="size-2 rounded-full bg-yellow-500 animate-pulse"></div>
</div>
</div>
</div>
</div>
</section>
<aside class="bg-slate-50 dark:bg-[#0c0c16] border-t border-slate-200 dark:border-border-dark p-4 shrink-0">
<div class="flex items-center justify-between mb-2">
<p class="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">JSON Step Definition</p>
<span class="material-symbols-outlined text-slate-400 text-sm cursor-pointer hover:text-primary">content_copy</span>
</div>
<div class="bg-white dark:bg-[#111122] rounded-lg border border-slate-200 dark:border-border-dark p-3 font-mono text-[10px] leading-tight max-h-32 overflow-hidden relative">
<div class="text-blue-500 dark:text-blue-400">{</div>
<div class="pl-4">
<span class="text-purple-500">"intent"</span>: <span class="text-green-600">"Fill email"</span>, <br/>
<span class="text-purple-500">"selectors"</span>: [
                    <div class="pl-4">
<span class="text-green-600">"[data-qa='email-input']"</span>, <br/>
<span class="text-slate-500 italic">"//form/div[2]/input"</span>
</div>
                ]
            </div>
<div class="text-blue-500 dark:text-blue-400">}</div>
<div class="absolute inset-0 bg-gradient-to-t from-white dark:from-[#111122] via-transparent to-transparent pointer-events-none"></div>
</div>
<div class="mt-4">
<button class="w-full bg-primary hover:brightness-110 text-white font-bold py-3 rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-primary/20 transition-all">
<span class="material-symbols-outlined text-lg">auto_fix_high</span>
                AI Selector Processing
            </button>
<p class="text-[9px] text-center text-slate-500 dark:text-slate-400 mt-2 px-2">
                Cleans redundant selectors to maintain essential, resilient identifiers.
            </p>
</div>
</aside>
</main>
<footer class="bg-white dark:bg-background-dark border-t border-slate-200 dark:border-border-dark px-4 py-2 flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400">
<div class="flex items-center gap-3">
<div class="flex items-center gap-1">
<span class="size-1.5 rounded-full bg-accent-green"></span>
<span>AI Ready</span>
</div>
<span class="opacity-50">|</span>
<span>Grouping Active</span>
</div>
<div class="flex items-center gap-2">
<span class="material-symbols-outlined text-[14px]">bolt</span>
<span>Low Latency</span>
</div>
</footer>

</body></html>

