# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
Describe the overall goal in 2 to 3 sentences.

> DocuBot answers developer questions about a codebase using the project's own documentation (`docs/`). It aims to give answers that are grounded in those docs and to say "I do not know" when the docs don't cover the question.

**What inputs does DocuBot take?**  
For example: user question, docs in folder, environment variables.

> A developer question, the `.md`/`.txt` files in `docs/`, and (for Modes 1 and 3) a `GEMINI_API_KEY` environment variable.

**What outputs does DocuBot produce?**

> Mode 1: a free-form LLM answer. Mode 2: up to 3 raw doc sections, each labelled with its filename. Mode 3: an LLM answer built from those sections that cites the files it used. Modes 2 and 3 return "I do not know based on these docs." when retrieval finds no meaningful evidence.

---

## 2. Retrieval Design

**How does your retrieval system work?**  
Describe your choices for indexing and scoring.

- How do you turn documents into an index?
- How do you score relevance for a query?
- How do you choose top snippets?

> - **Chunking:** each doc is split into one section per markdown heading (`#`, `##`, `###`). A section runs from its heading to the next one. Sections are about 200–530 characters and keep their title, e.g. `## Token Generation` or `### GET /api/users`.
> - **Tokenizing:** lowercase, keep runs of letters/digits/underscores (so `generate_access_token` stays one word), drop a small stopword list ("the", "is", "where", ...).
> - **Index:** an inverted index mapping each word to the positions of the sections that contain it.
> - **Scoring:** for each distinct query word, add how many times it appears in the section.
> - **Selection:** use the index to collect sections sharing at least one query word, score them, drop any below `MIN_SCORE = 2`, sort by score (ties broken by position in the docs), and return the top 3.

**What tradeoffs did you make?**  
For example: speed vs precision, simplicity vs accuracy.

> Simplicity over accuracy. Exact word matching is easy to explain and debug, but it misses related forms ("connect" vs "connection", "stored" vs "stores"). Heading-based chunks are focused and readable, but a section that answers the question without repeating its words can lose to a section that just mentions them often. Raw counts also favour longer sections.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  
Briefly describe how each mode behaves.

- Naive LLM mode:
- Retrieval only mode:
- RAG mode:

> - **Naive LLM mode:** calls Gemini once per question. Note: `naive_answer_over_full_docs` builds its prompt from the question only. The `all_text` argument is ignored, so the model never sees the docs and answers from general knowledge.
> - **Retrieval only mode:** never calls the LLM. It prints the top retrieved sections, or refuses.
> - **RAG mode:** runs the same retrieval first. If retrieval returns nothing, it refuses without calling Gemini. Otherwise it sends only the retrieved sections plus the question.

**What instructions do you give the LLM to keep it grounded?**  
Summarize the rules from your prompt. For example: only use snippets, say "I do not know" when needed, cite files.

> The RAG prompt (in `llm_client.py`) tells the model to use only the information in the snippets, never invent functions, endpoints or config values, reply exactly "I do not know based on the docs I have." when the snippets aren't enough, and name the files it relied on.

---

## 4. Experiments and Comparisons

Run the **same set of queries** in all three modes. Fill in the table with short notes.

You can reuse or adapt the queries from `dataset.py`.

> **Status:** the Mode 2 column comes from real runs. Modes 1 and 3 have not been run yet (this environment has no `GEMINI_API_KEY` and `google-genai` isn't installed). Fill in those columns after running `python main.py`.

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | _TODO: run Mode 1_ | Helpful. Top hit is `AUTH.md › ## Token Generation`, which names `generate_access_token` in `auth_utils.py`. The other 2 hits are related but noisy. | _TODO: run Mode 3_ | Mode 1 can't know `auth_utils.py`; expect a generic JWT answer. |
| How do I connect to the database? | _TODO_ | Partly helpful. Returns `SETUP.md › ## 3. Initialize the Database`, `# Database Guide`, `## Overview`. Misses `## Connection Configuration` (the `DATABASE_URL` answer) because "connect" ≠ "connection". | _TODO_ | Retrieval miss: RAG can only be as good as these sections. |
| Which endpoint lists all users? | _TODO_ | Helpful. Top hit is `API_REFERENCE.md › ### GET /api/users`. | _TODO_ | |
| How does a client refresh an access token? | _TODO_ | Helpful but hard to read. Top hit `AUTH.md › ## Client Workflow` mentions `/api/refresh` in step 4, but you have to scan for it. Misses `API_REFERENCE.md › ### POST /api/refresh`. | _TODO_ | |
| Which fields are stored in the users table? | _TODO_ | Harmful-ish. Returns `### GET /api/users` and `DATABASE.md › ### projects` (the wrong table). The real `### users` section scores 1 and is dropped by the threshold. | _TODO_ | Strong candidate for "RAG still fails". |
| Is there any mention of payment processing in these docs? | _TODO_ | Correct refusal: "I do not know based on these docs." | _TODO_ (should refuse without calling Gemini) | |

**What patterns did you notice?**  

- When does naive LLM look impressive but untrustworthy?  
- When is retrieval only clearly better?  
- When is RAG clearly better than both?

> _TODO after running Modes 1 and 3._ Things to look for:
> - **Naive confident but weakly grounded:** since the prompt never includes the docs, any project-specific answer (function names, env vars, routes) is a guess. "Where is the auth token generated?" is a good test.
> - **Retrieval only accurate but hard to read:** "How does a client refresh an access token?" returns the right section, but the answer is one line inside a numbered list.
> - **RAG combining clarity and evidence:** expect a one-line answer citing `AUTH.md` for the auth-token question.
> - **RAG still fails:** "Which fields are stored in the users table?" gets the `projects` table section, so RAG will either refuse or describe the wrong table.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  
For each one, say:

- What was the question?  
- What did the system do?  
- What should have happened instead?

> **Failure case 1:** "Which fields are stored in the users table?" Retrieval returned `### GET /api/users` and `DATABASE.md › ### projects`. It should have returned `DATABASE.md › ### users` (user_id, email, password_hash, joined_at). That section says "Stores basic account information", which doesn't exactly match "stored" or "fields", so it scored 1 and fell under `MIN_SCORE`.

> **Failure case 2:** "How do I connect to the database?" Retrieval returned general database sections and missed `## Connection Configuration`, which holds the actual answer (`DATABASE_URL`). Cause: "connect" and "connection" are different words to an exact-match scorer.

> **Failure case 3 (before the threshold):** "Is there any mention of payment processing in these docs?" returned `SETUP.md` because the word "docs" matched the heading "Using the Docs Assistant". It should refuse. With `MIN_SCORE = 2` it now does.

**When should DocuBot say “I do not know based on the docs I have”?**  
Give at least two specific situations.

> - The topic isn't in the docs at all (payment processing, Kubernetes deployment, the weather).
> - Only incidental words match, e.g. a single hit on a generic word like "docs" or "app", with nothing about the actual subject.
> - (RAG) The retrieved sections are on-topic but don't contain the specific fact asked for.

**What guardrails did you implement?**  
Examples: refusal rules, thresholds, limits on snippets, safe defaults.

> - **Score threshold:** `MIN_SCORE = 2` in `docubot.py`. `retrieve` drops any section scoring below it. If nothing is left, both Mode 2 and Mode 3 return "I do not know based on these docs." and Mode 3 never calls the LLM. The check lives in `retrieve` so every mode that uses retrieval gets it.
> - **Snippet limit:** at most 3 heading-sized sections, which keeps context small and focused.
> - **Prompt rules:** the RAG prompt requires an exact refusal string and file citations.

---

## 6. Limitations and Future Improvements

**Current limitations**  
List at least three limitations of your DocuBot system.

1. Exact word matching: no stemming or synonyms ("connect"/"connection", "stored"/"stores").
2. Raw term counts favour sections that repeat common words. For example, "Which endpoint returns all users?" ranks `DATABASE.md › ## Query Helpers` above `### GET /api/users`.
3. `MIN_SCORE` is a fixed count, so a long section with two incidental matches still passes, and a short, exactly-right section with one match is refused.
4. Naive mode never sends the docs to the model, so its answers are ungrounded by design.

**Future improvements**  
List two or three changes that would most improve reliability or usefulness.

1. Light normalization (strip plural and -ed/-ing endings), or embeddings, so related word forms match.
2. Weight rare words higher than common ones (TF-IDF style) and count heading matches extra.
3. Base the threshold on query coverage (fraction of distinct query words found) instead of a raw count.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
Think about wrong answers, missing information, or over trusting the LLM.

> A developer could act on a confident but wrong answer, such as the wrong env var name, the wrong table schema or a made-up endpoint, especially from naive mode, which never sees the docs. Retrieval misses (failure cases 1 and 2) can also make RAG refuse or answer from the wrong section, even when the docs do contain the answer.

**What instructions would you give real developers who want to use DocuBot safely?**  
Write 2 to 4 short bullet points.

- Prefer RAG or retrieval-only answers, and check the cited file before acting.
- Treat "I do not know" as a signal to read the docs directly, not as proof the answer doesn't exist.
- Don't use naive mode for project-specific facts.
