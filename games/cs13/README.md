# Counter-Strike 1.3 — Modern Rebuild

A playable, single-file browser FPS that recreates the feel of **Counter-Strike 1.x**
using nothing but modern web platform APIs. No engine, no libraries, no external
assets — the whole thing is one `index.html`.

> This is a fan tribute / tech demo, not affiliated with Valve. It borrows the
> *vibe* (de_dust sandstone, the corner HUD, the buy menu, terrorist hunt) — no
> original game code, art, or sound is used. Everything is generated at runtime.

## Play

Open `index.html` in any modern desktop browser (Chrome, Firefox, Edge, Safari)
and click **Deploy**. That's it — no build step, no server needed.

```
# optional: serve it locally
npx serve games/cs13     # then open the printed URL
```

## Controls

| Key | Action |
|-----|--------|
| `W` `A` `S` `D` | Move |
| Mouse | Look (click the canvas to lock the pointer) |
| Left click | Fire |
| `R` | Reload |
| `1` / `2` / `3` | Knife / pistol / rifle |
| `B` | Buy menu |
| `Shift` | Walk (slower) |
| `Esc` | Release the mouse |

## How it works

Everything is procedural and self-contained:

- **Renderer** — a from-scratch [raycasting engine](https://lodev.org/cgtutor/raycasting.html)
  (DDA wall casting + a per-column z-buffer for correctly-occluded billboard sprites),
  drawn to a low internal resolution and scaled up for the chunky retro look.
- **Textures** — sandstone, crates, blue metal and stone are painted onto
  offscreen canvases at load time (no image files).
- **Enemies** — billboarded terrorist sprites drawn in code, with line-of-sight
  chasing and shooting AI.
- **Audio** — every gunshot, reload, hit and jingle is synthesized live with the
  Web Audio API (no sound files).
- **Gameplay** — wave-based terrorist hunt with a CS-style economy: kills earn
  cash, spend it in the buy menu on armor, rifles, ammo and med kits. Each wave
  adds more Ts.

## Structure

A single `index.html` holds the markup, the token-based CSS design system
(dust palette, condensed HUD numerals), and the engine. It's intentionally one
file so it can be dropped anywhere and just run.
