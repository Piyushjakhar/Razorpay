# Feature Flag Service — Plan

## 1. Scope

In-process feature flag SDK in **Python**. Application embeds it, calls `evaluate(env, flag_name, context)`, gets a value. Config lives in an in-memory store; SDK keeps a local snapshot and stays in sync via pub/sub.

---

## 2. Resolved Ambiguities (from spec §1.2)

| Question | Decision | Rationale |
|---|---|---|
| **Bucketing key** | `hash(user_id + tenant_id + bucketing_key)` where `bucketing_key` defaults to `flag_name`. Flags can override with an optional `bucketing_group` field to opt into shared cohorts. | Spec requires independent buckets by default, shared on opt-in. Mixing `flag_name` in by default gives independence; `bucketing_group` is the explicit sharing knob. |
| **Targeting vs rollout precedence** | Targeting rules evaluated first; first match wins. Only if no rule matches does percentage rollout apply. Default value is the final fallback. | Matches user intent and standard industry convention (LaunchDarkly, Unleash). |
| **Misconfiguration handling** | **Both**: validate at `update_flag()` time and reject with a typed exception, AND defensively return `default_value` at evaluation time if a bad config somehow leaks through. | Defense-in-depth. Spec §1.1.6 says evaluation must never throw — so the eval-time safety net is non-negotiable regardless of validation. |
| **Config propagation** | Pub/sub (push). Store notifies registered SDK subscribers synchronously on every `set()`. | <5s budget is trivial with synchronous in-process callbacks. No polling complexity. |
| **Update write order** | **Cache first, then store.** SDK's `update_flag()` updates the local snapshot before calling `store.set()`. | User preference. Tradeoff noted in §6.1. |
| **Targeting rule grammar** | Simple `attribute == value` only. No AND/OR, no operators like `in`/`>`/`contains`. | Covers ~80% of real-world rules; keeps v1 scope tight. Easy to extend later. |
| **Rollout semantics for non-bool flags** | Rolled-in users get `rollout_value`; rolled-out users get `default_value`. No multi-variant rollouts. | Simplest model; matches user choice. |

---

## 3. Architecture

```
        ┌─────────────────────────────────────────┐
        │       FlagService (SDK, in-process)     │
        │                                         │
  ──▶ evaluate()  ─▶ Evaluator ─▶ Bucketer        │
        │                │                        │
        │                ▼                        │
        │            LocalCache                   │  ◀── reads (eval path)
        │             (env, name) → FlagConfig    │
        │                ▲                        │
        └────────────────┼────────────────────────┘
                         │ subscriber callback
        ┌────────────────┴────────────────────────┐
        │     InMemoryConfigStore                 │
        │       set(env, config)                  │
        │       get(env, name)                    │
        │       subscribe(callback)               │
        └─────────────────────────────────────────┘
```

**Components**

- `InMemoryConfigStore` — source of truth. Thread-safe dict keyed by `(env, flag_name)`. Maintains a list of subscriber callbacks; invokes them on every successful `set()`.
- `LocalCache` — SDK's in-process snapshot. Same shape as the store. Read by the evaluator; written by both `update_flag()` (direct) and the store subscriber (for changes that originated elsewhere).
- `Evaluator` — pure function `(FlagConfig, EvaluationContext) → value`. Implements the precedence ladder. Wrapped in a top-level try/except that returns `default_value` on any unexpected error.
- `Bucketer` — pure function `(user_id, tenant_id, bucketing_key) → int in [0, 100)`. SHA-1 of `"{user_id}:{tenant_id}:{bucketing_key}"`, truncated to first 8 hex chars, mod 100.
- `Validator` — invoked on `update_flag()`. Raises `InvalidFlagConfig` for any spec violation.

---

## 4. Data Model

```python
@dataclass(frozen=True)
class TargetingRule:
    attribute: str      # e.g. "country"
    value: Any          # e.g. "IN"
    return_value: Any   # value when this rule matches

FlagType = Literal["bool", "string", "int"]

@dataclass(frozen=True)
class FlagConfig:
    name: str
    type: FlagType
    default_value: Any                  # returned when no rule matches and user not in rollout
    targeting_rules: tuple[TargetingRule, ...] = ()
    rollout_percentage: int = 0         # 0..100
    rollout_value: Any = None           # required if rollout_percentage > 0
    bucketing_group: str | None = None  # opt-in shared cohort key

@dataclass(frozen=True)
class EvaluationContext:
    user_id: str
    tenant_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
```

Environment is not part of `FlagConfig` — it's the outer key. Same flag name in `dev` vs `prod` is two independent configs.

---

## 5. Evaluation Algorithm

```python
def evaluate(env, flag_name, context):
    config = cache.get(env, flag_name)
    if config is None:
        log.error("flag_not_found", flag=flag_name, env=env)
        return None  # caller's responsibility to handle unknown flag

    try:
        # Step 1: targeting rules (first match wins)
        for rule in config.targeting_rules:
            if context.attributes.get(rule.attribute) == rule.value:
                return rule.return_value

        # Step 2: percentage rollout
        if config.rollout_percentage > 0:
            key = config.bucketing_group or config.name
            bucket = bucketer.bucket_for(context.user_id, context.tenant_id, key)
            if bucket < config.rollout_percentage:
                return config.rollout_value

        # Step 3: default
        return config.default_value

    except Exception as e:
        log.error("flag_eval_error", flag=flag_name, env=env, error=str(e))
        return config.default_value
```

**Invariant:** `evaluate()` never raises. Worst case: returns `default_value` (or `None` if flag doesn't exist).

---

## 6. Configuration Lifecycle

### 6.1 Update path (writes)

```python
def update_flag(env, config):
    validator.validate(config)     # raises InvalidFlagConfig on bad input
    cache.set(env, config)         # (1) cache first — eval sees new value immediately
    store.set(env, config)         # (2) then store — also triggers subscribers
```

**Tradeoff:** "cache first, then store" means if the store write fails, the cache holds a value the store doesn't. For an in-memory store this is effectively impossible, but worth flagging. The reverse order (store first, cache via subscriber) is more standard for distributed systems but adds eval-path latency. Sticking with user's preference.

The store's subscriber callback also writes to cache — this is idempotent (writing the same `FlagConfig` is a no-op), so the double-write is harmless.

### 6.2 Read path (evaluation)

`Evaluator` reads exclusively from `LocalCache`. Never touches the store on the hot path. This keeps `evaluate()` O(1) lookup + O(rules) loop.

### 6.3 Initial sync + ongoing propagation

On SDK construction:
1. Pull all flags from store, populate cache.
2. Register subscriber: `store.subscribe(on_flag_changed)`.
3. On callback: `cache.set(env, config)`.

Propagation latency: synchronous callback dispatch, microseconds. Well under the 5s budget.

---

## 7. Bucketing

```python
def bucket_for(user_id, tenant_id, bucketing_key) -> int:
    raw = f"{user_id}:{tenant_id}:{bucketing_key}".encode()
    digest = hashlib.sha1(raw).hexdigest()
    return int(digest[:8], 16) % 100  # 0..99
```

**Properties this guarantees:**

1. **Sticky** — same `(user, tenant, key)` → same bucket forever. No per-user state needed.
2. **Independent by default** — `bucketing_key = flag_name`, so flag A's 30% cohort and flag B's 30% cohort are different slices.
3. **Shared on opt-in** — set `bucketing_group="early_access"` on multiple flags → they all hash with the same key → same cohort.
4. **Monotonic ramping** — increasing `rollout_percentage` from 30 → 50 keeps existing in-users (buckets 0–29 ⊂ buckets 0–49). Users never flip back out.
5. **Uniform distribution** — SHA-1's avalanche property gives ~uniform spread over `[0, 100)`.

Hash choice: SHA-1 is non-cryptographic here, just used for uniform distribution. MD5 or xxhash would work equally well; SHA-1 is in stdlib.

---

## 8. Validation Rules (`InvalidFlagConfig`)

Rejected at `update_flag()`:

- `rollout_percentage` not in `[0, 100]`
- `type` not in `{"bool", "string", "int"}`
- `default_value` does not match declared `type`
- `rollout_value` does not match declared `type` (when rollout > 0)
- Any `TargetingRule.return_value` does not match declared `type`
- `rollout_percentage > 0` but `rollout_value is None`

All raise `InvalidFlagConfig` with a human-readable message. No partial updates — validation runs before any cache or store mutation.

---

## 9. Concurrency

Python, single process. GIL makes `dict` operations atomic, but we still need write-then-publish atomicity.

- `LocalCache` and `InMemoryConfigStore` each use `threading.RLock` for writes.
- Reads on `LocalCache` are lock-free (atomic dict read). `FlagConfig` is frozen, so no torn reads.
- Subscriber dispatch happens synchronously inside `store.set()` while the store lock is held — keeps the "set + notify" pair atomic. Subscribers should be fast (just `cache.set`).

---

## 10. Public API

```python
# Construction
service = FlagService(store: InMemoryConfigStore)

# Admin
service.update_flag(env: str, config: FlagConfig) -> None
service.get_flag(env: str, name: str) -> FlagConfig | None

# Evaluation
service.evaluate(env: str, name: str, context: EvaluationContext) -> Any
# Typed helpers (optional, for ergonomics):
service.evaluate_bool(env, name, context) -> bool
service.evaluate_string(env, name, context) -> str
service.evaluate_int(env, name, context) -> int
```

---

## 11. Test Plan (spec §1.1.8)

Each row → one or more pytest test cases.

| # | Area | Test |
|---|---|---|
| 1 | Flag types | bool/string/int return correctly typed values |
| 2 | Targeting rules | Matching rule returns rule value; no match → default; first match wins among multiple |
| 3 | Stickiness | Same `(user, tenant)` returns same answer across 1000 calls |
| 4 | Independent buckets | Two flags both at 30%, no `bucketing_group` → cohorts differ (statistical, not identical) |
| 5 | Shared buckets | Two flags both at 30% with same `bucketing_group` → identical cohort |
| 6 | Monotonic ramp | Users in at 30% are still in at 50% |
| 7 | Environment isolation | Same flag name in dev vs prod, different configs → independent evaluations |
| 8 | Default-on-error | Inject a corrupt rule (bypassing validation) → eval returns default, logs error |
| 9 | Validation | `update_flag` raises on each invariant violation in §8 |
| 10 | Precedence | Flag with both targeting rule and rollout → matching rule wins; non-matching → falls to rollout |
| 11 | Live update | `update_flag` → next `evaluate()` returns new value (effectively immediate) |
| 12 | Eval never throws | Missing attributes, weird contexts — returns default, never raises |

---

## 12. Implementation Milestones (~70 min budget)

Commit at each milestone. Tests are the unit of progress.

| M | Time | Deliverable |
|---|---|---|
| M1 | 10 min | Data model + `InMemoryConfigStore` + `LocalCache` + skeleton `FlagService`. Test: store/cache roundtrip. |
| M2 | 10 min | Evaluator with default-only path. Tests 1, 12. |
| M3 | 10 min | Targeting rules. Tests 2, 10 (partial). |
| M4 | 15 min | Bucketer + percentage rollout + `bucketing_group`. Tests 3, 4, 5, 6, 10 (full). |
| M5 | 10 min | Validator + fail-safe wrapper. Tests 8, 9. |
| M6 | 10 min | Pub/sub propagation + multi-env. Tests 7, 11. |
| M7 | 5 min | Polish, cleanup, README of public API. |

Then pause for the interviewer's extension at ~minute 70.

---

## 13. Out of Scope (spec §1.3)

- Persistent storage
- Admin UI
- Network transport (config delivery is in-process)
- Multi-region replication
- Multi-variant rollouts (only binary rollout in v1)
- Rich rule grammar (AND/OR, operators beyond `==`)
- Metrics/observability beyond the structured error log
