# 1. Problem Statement

Build an in-process Feature Flag Service that an application can embed and query at runtime. The service decides, for a given flag and a given evaluation context (user, tenant, request attributes), what value to return.

### 1.1. Core Functional Requirements

1. Flag types: boolean, string, integer. Flags have a name, a default value, and a value type.
2. Targeting rules: a flag's evaluation can return different values based on attributes of the evaluation context (e.g., `country == "IN"` → `true`, otherwise `false`).
3. Percentage rollouts: a flag can be rolled out to N% of users. Same user must consistently get the same answer across calls (sticky bucketing). Same user must also get the same bucket *across different flags' rollouts* of the same percentage scheme only if the flag is configured to share the bucketing key - otherwise buckets must be independent. (Resolve ambiguity in your plan.)
4. Environments: flags are defined per environment (e.g., `dev`, `staging`, `prod`). The same flag can have different configurations across environments.
5. Live updates: flag configuration must be updatable at runtime without a service restart. Update propagation latency budget: under 5 seconds.
6. Evaluation API: synchronous, low-latency. Must never throw to the caller; on internal error, return the flag's default value and emit a structured error log.
7. Configuration source: assume an in-memory config store with a method `set(flag_config)` and `get(flag_name, env)`. You decide how the SDK consumes it.
8. Tests: unit tests covering flag types, targeting rules, percentage stickiness, environment isolation, default-on-error.

### 1.2. Required Behaviors You Must Resolve in Your Plan

These are deliberately ambiguous. Decide and justify in `PLAN.md`:

- What is the bucketing key for percentage rollouts? (User ID? Hash of user ID + flag name? Tenant + user?)
- What happens when targeting rules and percentage rollout are both defined on the same flag? Which takes precedence?
- What happens on misconfiguration (e.g., percentage > 100, type mismatch on rule value)? Reject at config time, fail-safe at evaluation time, or both?
- How does the SDK consume config updates - pull (poll), push (subscribe), or both?

### 1.3. Out of Scope

- A real persistent store (in-memory is fine).
- A UI / admin panel.
- Network/transport layer (treat config delivery as an in-process API).
- Multi-region replication.

---

## 2. Process Requirements

- Write `PLAN.md` first. Walk the interviewer through it before invoking your agent for implementation.
- Commit incrementally. The git log is part of the deliverable.
- Tests are the unit of progress. No "done" without green tests.
- The interviewer will introduce an extension around minute 70. Plan your time accordingly.
