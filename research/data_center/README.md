# Data Center Reliability Research v0.1

Research-only extension of Genesis for a second measurable-system domain.

## Scope

This first experiment covers operational reliability signals only:
- rack inlet temperature
- rack outlet/inlet thermal delta
- UPS load
- UPS battery level
- rapid power changes
- environmental humidity

It does **not** control equipment, issue shutdown commands, optimize cooling, or perform cybersecurity analysis.

## Design principle

The data-center layer emits evidence candidates. Shared Genesis mechanisms can later organize these observations, quality findings, patterns, incidents, actions and outcomes.

No production Genesis decision thresholds or robot-specific behavior were changed.
