# R5: original EIS notice XML selection diagnostics

The private operator evidence API never treats a 223-FZ or manual upload as a
44-FZ original. Even for authentic 44-FZ XML, a registry number may match
several mutually different archived notice revisions. File order cannot prove
which revision is legally current. No business or risk decision is justified
by selecting a random first file.

The v1 evidence API now returns non-sensitive source_selection status:
- unsupported_source
- no_unique_registry_matched_xml
- ambiguous_notice_revisions
- single_registry_matched_xml

source_candidate_count is the number of safely parsed, registry-matched
original XMLs, not number of verified claims, and does not expose filenames,
private source text, legal entity details or content. Unknown facts remain
UNKNOWN with no fictitious evidence on ambiguity.

The current private source inventory finds multiple distinct XML versions
with no trustworthy version marker in several stored 44-FZ runs. This patch
does not guess a current version, change reported bid decisions or send
requests to EIS. The model can be used only to surface review questions;
original revision resolution needs verified SOAP metadata and operator review.
