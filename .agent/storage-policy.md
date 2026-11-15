# Tender Agent research storage

- Bulk source captures, originals, indexes' staging files, research artifacts, TA backup snapshots and historical Data Platform backups belong on mounted `/Volumes/ArvectumSSD/Arvectum/storage/`, not the internal SSD.
- The 2026-11-15 migration targets `/Volumes/ArvectumSSD/Arvectum/storage/tender-agent-safe-20261115`. Compatibility paths may point there only after checked cutover. Check the actual mount and device, not just a directory name.
- Retain internal Market Intelligence live acceptance workspace and a bounded set of fresh, independently verified Data Platform backups because the existing preflight requires trusted internal APFS. Historical copies must be archived and hash-verified before removing redundant local copies. Never weaken a mutation gate to force migration.
- Check free space on both internal and external volumes; do not start duplicate collectors or relocate a live DB transaction. If external storage is missing/unhealthy, stop bulk writers rather than silently filling the internal disk.
