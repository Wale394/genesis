# Genesis Context Shift Stress Test v0.1

## Purpose

Test whether Genesis can distinguish a signal deviation from a change in operating context.

This is an **experiment**, not yet a core Genesis contract.

## Four cases

1. Normal signal + stable context -> `NORMAL`
2. Signal deviation + changed context -> `CONTEXTUAL_DEVIATION`
3. Signal deviation + stable context -> `BEHAVIORAL_DEVIATION`
4. Signal deviation + unknown material context -> `INSUFFICIENT_CONTEXT` + investigation required

## Critical rule

> UNKNOWN context is not treated as stable context.

A deviation with unknown material context must not be promoted to behavioral abnormality by this experiment.

## Why this matters

A temperature rise can be caused by legitimate changes in load, motion, power, environment, or operating mode. Genesis therefore needs to distinguish:

`signal changed` from `system behavior changed unexpectedly`.

## Promotion criterion

Do not integrate this evaluator into the core reasoning engine until experiments demonstrate that the distinction is useful across multiple signals, domains, and realistic context changes.
