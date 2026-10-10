
# GENESIS Evidence Independence & Common-Mode Stress Test v0.1

## Architectural question

Two measurements can agree and still fail to provide independent confirmation.

Examples:
- two sensors share a controller;
- two measurements are derived from the same raw observation;
- two signals travel through a common acquisition chain;
- dependency information is simply unknown.

## Expected reasoning

```text
Distinct physical signals
        +
Separate infrastructure
        ↓
CORROBORATING

Distinct signals
        +
Shared infrastructure
        ↓
COMMON_MODE_RISK

Unknown dependency
        ↓
INSUFFICIENT_INDEPENDENCE

Different physical locations
        ↓
CONTEXTUAL_DIFFERENCE
```

## Important conclusion

`UNKNOWN != INDEPENDENT`

and:

`AGREEMENT != INDEPENDENT CORROBORATION`

The experiment intentionally does not attempt to calculate a universal independence score.

## Integration decision

Do not integrate this experiment into the core yet. First extend the stress test to:
- dependency chains;
- derived measurements;
- more than two evidence items;
- shared power/network/controller dependencies;
- contradictory dependency metadata;
- robotics, energy infrastructure, and industrial equipment.
