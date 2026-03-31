# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A single-file web game (`tictactoe.html`) — no build step, no dependencies, no package manager. Open the file directly in a browser to play.

```bash
open tictactoe.html
```

## Architecture

Everything lives in one HTML file with three co-located sections:

- **`<style>`** — All visual design using CSS custom properties defined in `:root`. Colors, glows, and animations are controlled via variables (`--x-color`, `--o-color`, `--x-glow`, `--o-glow`, etc.), so visual changes should go through those vars rather than scattered hardcoded values.

- **`<body>`** — Static shell only: `.container > .scoreboard`, `.status`, `#board` (empty), `.buttons`. The board cells are **not** in the HTML — they are injected by JS on every state change.

- **`<script>`** — Vanilla JS, no framework. Core state is three variables: `board` (9-element array, `null | 'X' | 'O'`), `current` (whose turn), `gameOver`. `buildBoard()` tears down and rebuilds all 9 `.cell` elements from scratch on every move — this is intentional to keep animation re-triggers clean.

## Key patterns

- **Win detection** — `WINS` is a hardcoded array of the 8 winning index triples. `getWin()` checks them after every move.
- **Ghost preview** — Empty cells show a faint version of the current player's mark on hover via CSS (`.cell:not(.taken):hover .mark { opacity: 0.2 }`). The mark element is always rendered with the current player's symbol; CSS controls visibility.
- **Status classes** — `setStatus(text, cls)` swaps the class on `#status` between `x-turn`, `o-turn`, `win`, and `draw` to drive color and dot-glow changes purely via CSS.

## Git workflow

Commit all changes with clean messages and push to `origin/main` (GitHub: `Subriti/tic-tac-toe`) after each meaningful change.
