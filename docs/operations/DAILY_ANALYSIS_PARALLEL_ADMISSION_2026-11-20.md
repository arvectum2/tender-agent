# Parallel analysis and historical acquisition

One existing-item recovery analysis keeps the daily and run-level execution
guards and the exclusive heavyweight compute slot. While generation and
manager synthesis run against read-only transactions, it does not retain the
historical priority, mutation or backup locks. Network acquisition and light
source-bound writers can proceed independently under their own existing
admission rules. A second GPU-heavy process is still excluded by design,
particularly with memory pressure and sustained GPU saturation.

Immediately before persisting the report and atomic history/item/digest,
the operator reacquires priority and mutation leases and fresh MI/PITR
prewrite proof. The original exact target, source and profile are checked
again under the write fence. Actual contention may wait up to 120 seconds;
all acquired write leases are released between attempts. No prewrite error
or possibly executed business write is automatically retried. The generation
journal records separate generation and write-admission evidence.

No changes to consent, source permissions, active report, existing
historical receipts, or the index batch admission contract. No migrations.
The original in-flight operator uses the previous release and must finish
naturally before cutover. Independent archive capture can overlap LLM;
heavy historical extraction/indexing remains serialized until resource
coordination is explicitly redesigned and tested. Under the observed
GPU 99% and memory pressure, simultaneous heavy work is not justified.

Do not restart a blocked collector until its exact committed source receipts
and DB linkage are reconciled. The historical archive loader currently has
5272/5272 compressed targets attempted; this is not proof of overall source
coverage. The read-only reconciliation must establish whether any remaining
capture work exists. Do not reset blocked state blindly.
