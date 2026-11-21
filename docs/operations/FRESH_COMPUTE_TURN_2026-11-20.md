# Fresh compute turn

Live analysis on b31ff64e timed out acquiring the heavy slot before generation:
the historical worker immediately reacquired at a batch boundary. The shared
heavy slot alone is not a scheduling protocol.

The two-sided change introduces an independent fresh-compute-turn.lock.
History probes it with a short shared lease while trying to acquire the heavy
slot. A fresh analysis holds the exclusive turn while waiting, at most 600 s,
then releases the turn and retains only the heavy lease through generation and
the protected commit. History completes an admitted batch without interruption.
No priority, mutation or backup fence is held during queued waiting/generation.
All previous resource checks, atomic commit, MI and PITR proof remain required.

Coordinated rollout only: create the dedicated regular owner-only lock in the
resource directory during reviewed activation. Use clean pinned research
candidate d632b81d269ac4f999dcaaf1e58cf8d1046693b1, separate from existing worker
checkout. Drain current history at a verified boundary for a one-time service
configuration update. Preserve prior launcher/config and state for rollback.
Do not activate production until the exact paired historical worker is ready.
Do not substitute a lock or forcibly unlock any active worker. New compatible
processes must use the same lock inode; never unlink/replace it while running.
Revalidate backup, CI, immutable release and source admission. Re-plan the
failed exact target with new release digest. The isolated cross-process test
proved ordering, not live completion. Network capture remains independent;
GPU-heavy extraction and generation remain serialized.
