# TDP R3: fail-closed saved original file reference

An operator run's metadata must not be treated as a trusted arbitrary filesystem path. The legacy loader and supplier quote collector now share one original-file resolver that requires a single safe stored basename, non-symlink input folder, a regular existing input file with an exact real parent, and no symlinks. This check occurs before reading extracted original documents or commercial quote inputs.

No tenant documents, evidence, original contents or source claims are rewritten. Existing safe upload filenames and demo run JSON formats stay unchanged. Invalid/compromised metadata fails closed, not by quietly loading unrelated filesystem content. Source-grounded report and frozen procurement semantics remain untouched.

32 relevant tests pass including regular intake, path/symlink/missing file cases, upload/report and EIS source fixtures. Owner private previews and watchdog remain untouched. Canonical TDP-REFACTOR-20261009 still in progress pending golden cases and visual signoff.
