# ADR 0003: Ask Relay retrieves with permission-aware search, not embeddings (yet)

- Status: accepted (2026-11-16)
- Relates to: Round 3 roadmap item "Ask Relay: workspace-wide cited answers, with pgvector retrieval"

## Context
Ask Relay answers questions about a whole workspace from records the asker may open. The
plan named pgvector retrieval. pgvector is installed in the database, but embeddings would
add a model call per record on every change, a backfill job, a second index that must obey
row-level security and evidence audiences, and a new failure mode when the embedding
provider is down. The workspaces Relay serves hold thousands of records, not millions, and
the questions people ask name the things they want ("webhooks", "refunds", "Arjun").

## Decision
`relay/intelligence/ask.py` retrieves with the existing workspace search, which already
applies every record's permissions and audience. It searches once for the whole question,
then once per keyword (stop words removed), ranks records by how many searches found them
(the exact phrase counts triple), and adds meeting decisions, actions, questions and risks
that mention a keyword. Knowledge bodies are attached as excerpts. The top 12 records become
the evidence; the model may cite only those, and `finalise` removes any other citation.

## Consequences
- No new index, job or provider dependency; retrieval can't leak what search wouldn't show.
- Paraphrased questions with none of the record's words can miss; the answer then says
  "not in the records" rather than guessing, and the matching records are still listed.
- **Trigger to add embeddings:** a workspace beyond about 20,000 searchable records, or more
  than 1 in 5 Ask questions ending in "not in the records" while a human finds an answer.
  Then: an `embedding` column on knowledge, meeting items and work items (pgvector),
  filled by an outbox job, queried with the same permission filters, and blended with the
  keyword score.
