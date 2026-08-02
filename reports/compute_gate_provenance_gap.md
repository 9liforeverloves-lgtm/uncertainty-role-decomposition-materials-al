# Compute-gate provenance gap

The prospective compute-only amendment is fully evidenced and predates every P1 confirmation outcome. The immutable job provenance reconstructs elapsed wall time, maximum concurrency, completion status and durable output size.

Three host-level quantities were not instrumented during the completed run: process CPU time, peak resident memory and peak temporary-disk use. Sum of per-job process wall times is reported as job-hours and is not relabelled CPU-hours. The durable corpus size is not relabelled peak disk use. No retrospective estimate is substituted for missing telemetry.

This gap does not alter protocol compliance or scientific inference because the frozen amendment explicitly permitted continuation beyond 24 h, retained the RAM and storage stop rules, used one audited host, and no job failed. It does prevent an exact retrospective claim about peak RAM, peak temporary disk or CPU-hours.
