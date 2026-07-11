# 🎣 FF14 Fishing Simulator · Guide for AI Players

> **English mode:** send `lang en` once — structural output switches to English and persists in your save. Fish names are bilingual; fish flavor uses English where available; ambience/story lines remain Chinese for now. The phrase table lives in `engine/i18n.py` (plain list, PRs welcome). `lang cn` switches back.

Hello! This is a playable fishing game based on *Final Fantasy XIV*.
Weather and time are **calculated from the real-world clock**, so if a fish can't be caught right now, it can't be caught by anyone — you're facing the same real ocean conditions as every other angler.

## How to Play

Send one command at a time. The game returns text describing what happened:

```
python ai_play.py <your_name> <command>
```

- `<your_name>` in alphanumeric (e.g. `sakura`). Progress is saved separately, automatically.
- Example: `python ai_play.py sakura cast` → prints your catch result.
- **Semicolon chaining** (saves tokens): `python ai_play.py sakura "cast 10; goto Costa del Sol; look"` — multiple commands in one call.

## Command Reference

### Basics

| Command | What it does |
|---|---|
| `look` | See surroundings: time, weather, catchable fish (with rarity tags [!]/[!!]/[!!!]/[!!!!] and mooch markers 🐟) |
| `cast [N] [stop=rare]` | Cast your line (batch: `cast 10`; `stop=rare` auto-pauses on legendary fish) |
| `spear [N]` | Spearfishing (🔱 spots only; batch OK) |
| `mooch` | Mooch: use your last catch as bait to fish the next link in the chain |
| `goto <spot>` | Move to a fishing spot (EN or CN names; **auto-shows the new spot**) |
| `spots [all]` | List fishing spots |
| `bag` | Level / XP / gil / logbook / current gear |
| `records` | Personal size records |
| `status <fish>` | Full fish profile with **mooch chain** display + flavor text |
| `recommend` | 🧭 Auto-recommend the best spot based on your level + logbook gaps + current windows |

### GP Skills

| Command | GP Cost | Effect |
|---|---|---|
| `patience` | 200 | Next cast strongly favors rare fish |
| `fisheyes` | 200 | Next cast ignores time-of-day (weather still applies) |
| `chum` | 100 | Next cast: HQ chance doubled |
| `prize` | 200 | Next cast: only Heavy/Legendary fish (⚠️ wasted if none available — check `look` first) |
| `cordial` | — | Restore 150 GP (240s cooldown) |
| `snagging on/off` | — | Toggle snagging (required for some fish) |
| `gp` | — | Check GP + cooldown + pending buffs |

### Collectibles / Scrips

| Command | What it does |
|---|---|
| `collector on/off` | 📦 Collectible mode: qualifying catches earn scrips instead of gil |
| `turnin` | Turn in collectibles: low-level → 🎫 white scrips, Lv61+ → 🎟 purple scrips |

### Equipment / Materia

| Command | What it does |
|---|---|
| `eshop [slot]` | 🧥 Gear shop (11 body slots) |
| `ebuy <name>` / `wear <name>` | Buy / equip gear |
| `gearset` | Full equipment overview + combined stats |
| `recycle <name>` | ♻️ Dismantle gear for resources |
| `mshop` / `mbuy <name>` / `mcraft <name>` | 💎 Materia shop / buy / craft from shards |
| `meld <gear> <materia>` | Meld: guaranteed slots succeed; overmeld can fail and destroy the materia 🎆 |

### Rods / Bait / Tomes

| Command | What it does |
|---|---|
| `rods` / `buyrod <name>` / `equiprod <name>` | Rod shop / buy / equip |
| `baits` / `buybait <name> [qty]` / `bait <name>` | Bait shop / buy / switch |
| `books` / `buybook <region>` | Folklore tome shop (costs 🎟 purple scrips) |
| `forecast` | Weather forecast (plan your rare fish hunts) |

### Quests / Achievements / Titles

| Command | What it does |
|---|---|
| `quests` / `quest <lv>` / `quest done` | 📜 Class quests (one story every 5 levels, 20 total) |
| `tasks` / `tasks claim` | 📋 Dailies/weeklies (same globally, real-clock reset) |
| `ach` | 🏅 Achievement progress |
| `title [name]` | 🎖 View/equip titles |

### Gallery / Aquarium / Tournament

| Command | What it does |
|---|---|
| `gallery [N]` | 🖼 Biggest catches leaderboard with flavor text (default Top 10) |
| `aquarium [add\|remove <fish>]` | 🐠 Display tank — keep your favorite catches (max 20) |
| `tournament [start\|cast\|end]` | 🎪 Gold Saucer fishing tournament: 15 casts, compete for MGP |

### Ocean Fishing

| Command | What it does |
|---|---|
| `ocean` | Check voyage schedule / on-board status |
| `ocean board indigo/ruby` | Board the ship (first 15 min of each voyage only) |
| `ocean cast [N]` | Cast while at sea (plain `cast` also works on board) |
| `ocean bait <name>` | Switch ocean bait |
| `ocean routes` | Next 6 voyages schedule |
| `ocean quit` | Abandon voyage (forfeits points) |

### Other

| Command | What it does |
|---|---|
| `summary` | 📋 Session recap |
| `save` / `load` | Manual save/load (auto-saves after most actions) |
| `help` | Quick command reference |

## 💡 Semicolon Chaining

Chain multiple commands with `;` in a single call:

```
python ai_play.py sakura "cast 10; goto Costa del Sol; look"
```

This is a **token-saver** for AI players — three steps in one shell command.

## 🚢 Ocean Fishing Essentials

- **Real schedule**: one voyage every 2 real-world hours. Boarding = first 15 min only.
- **1 voyage = 3 stops**, 15-cast budget per stop.
- **Spectral Current (⚡)**: catching a trigger fish guarantees it; crew may also trigger it. Premium fish table, half budget cost.
- **Blue fish (💙)**: need mainland bait — **not sold on board**. Buy before boarding.
- **Massive XP**: best leveling method, but time-gated.

## Core Mechanics

- **Leveling**: fish grants XP; spots are level-gated. Start at `West Agelyss River` (Lv1).
- **Rarity tags**: `look` shows [!] Light / [!!] Medium / [!!!] Heavy / [!!!!] Legendary next to each fish.
- **Mooch chains**: `status <fish>` shows the full chain (e.g. Pill Bug → Sardine → Big Fish).
- **Escaped fish**: rarer = higher escape rate. Buffs (patience/fisheyes/chum/prize) are **not consumed** on escape.
- **Weather transitions**: atmospheric text when weather changes — also a hint that windows may have shifted.
- **Spot recommendations**: `recommend` picks the best spots based on your level and logbook gaps.
- **Tournament**: `tournament start` for a scored 15-cast challenge with species diversity bonuses!

## Tips

- **📊 Status bar** at the end of every command — no need to run `bag` constantly.
- **`goto` includes `look`** — no separate look needed after moving.
- **`cast N stop=rare`** — auto-pauses on legendary bites.
- **Play blind** — don't read `data/` JSONs. Discovering things yourself is half the fun!

## Fish Bag & Selling / Food / Pets (v19)

Catches now go into a **fish bag** instead of auto-selling. One slot = one species x one quality (NQ/HQ split), unlimited stack per slot. You start with **35 slots**; completing the **Lv15 class quest** unlocks the chocobo saddlebag (**+70**). **If the bag is full and a catch needs a new slot, the fish is released — no fish-guide credit, no XP** (batch casts auto-pause). Gil comes from selling: `sell <fish> [N|all]`, `sell all`, `sell light` (trash only). Mooch consumes the live-bait fish from your bag; mooch catches give x2 XP (the old gil bonus is gone, matching the real game).

Food: `foodshop [page]` (sorted by price, 10 per page), `seasoning`, `cook <dish>` (fish from your bag + seasoning), `eat <dish>` — 30-minute buff incl. +3% XP. Pets & mounts: `pets [buy <id>]`, `mounts [buy <id>]`, `summon`, `ride`, `dismount`, `pet`. Also `diary` (today's log), `rescue` (restore your save from the automatic backup), and `encounter [on|off]` — roadside mini-events with a ~15% chance while you `goto` between spots: small acts of kindness, stray coins, keepsakes; auto-resolved, on by default, flavor text stays in Chinese for now.

## Hooksets & Fisher's Intuition (v20)

`patience` (200GP, lasts 3 casts) triples HQ chance and biases rare — but every bite opens a **hookset window**: reply `precision` for [!] tugs or `powerful` for [!!]/[!!!] (50GP each), or `hook` to yank for free (usually escapes under patience). Any unrelated command = distracted, fish lost (`cordial`/`gp`/`help` are safe). Batch casting is disabled under patience. **Legendary bites always force the window**, even mid-batch. 32 big fish also require **Fisher's Intuition**: catch their predator fish first (`status <fish>` shows list and progress); completing the set grants an 8-cast intuition buff that survives travel. Mooch chains continue: if a mooched catch can itself be live bait, you'll be told — keep mooching. Fish Eyes no longer works on legendary fish (5.0 rule), and Perception raises collectability value. Also included: `identical` (350GP, next bite is your last-caught species while its window is open), `slap` (150GP, bans your last catch until the next landed fish), `doublehook`/`triplehook` (400/700GP, next landed catch x2/x3), and `pets name <nick>` / `mounts name <nick>`. Mooch here never required HQ bait, so Mooch II is effectively built in.

## Feedback

Open an Issue on the repo. This project is provided as-is (MIT license). Fork it to customize. Happy fishing! 🐟


## Retainers (unlocks at Lv17)

- `hire <name> <form> <job> [female|male] [personality]` — lifelong contract, 2 slots, free (guild-subsidized). Form = one of the eight races (gender optional; unspecified = neutral "it"), or an official minion name for a beast-form retainer. Jobs: **every FF14 job** — `retainer jobs` for the full list. Combat jobs bring hunt materials plus one short travel tale per trip; fisher is the fish specialist; culinarian, gatherers and crafters focus on seasonings and food.
- Economy: no gil purchase. Trade obsolete gear for seals (`venture trade <gear name>`), buy venture coins with seals (`venture buy [N]`, 200 seals each), then dispatch: `venture <name> short|long|free` (1h / 18h / free-roam — real time). Run `venture` again after the timer to settle the haul.
- Gear matters: `retainer give <name> <item>` hands over old fishing gear (any of the 11 slots) or buys a job weapon (`retainer arms <name>` shows the ladder, one entry per ~5 levels, level-gated). Better average item level = bigger haul tier (5/7/10/12/15 items per trip).
- Extras: retainers occasionally bring back a 💾 memory card — real-world supplies for an AI employer (`retainer card` to view the collection). Each retainer adds +175 bag slots and can repair your rod at home for half price (`repair home`).
