# AI Localization Checker

The tool captures screenshots of a mobile game (Unciv, Android emulator) in several languages and detects localization defects — truncated text, overlaps, untranslated strings — with a vision LLM. Its quality is measured against an OCR + translation-table baseline on a labeled dataset, together with the time it saves a QA engineer.

**Status:** Work in progress — Stage 0

## Problem

## Approach

## Results

The [Stage 1 vertical slice](docs/vertical-slice.md) runs both detectors and
replays matching and metrics offline. Its [issue #14 report](docs/evidence/14/report.md)
records observations on three variants of one screen, with reference gaps and
draft conclusions for human review; the numbers are not quality estimates.

## Limitations

## How this was built

The code is written with Claude Code; see the [decision log](docs/decisions.md) and the [bootstrap instructions](docs/bootstrap.md).
