# Licensing & Dataset References

**DiscoverMyRole — AI-Powered Intelligent Job Search and Career System**
IIT Madras · Data Science and AI Project · Group 4

---

## 1. Code License

The source code in this repository is released under the **MIT License**. See [`../LICENSE`](../LICENSE) for the full text.

MIT was selected because it is permissive, short, widely understood, and compatible with every dependency license listed in §4 — no dependency imposes a copyleft obligation that MIT would violate.

### What the license does and does not cover

| Covered | Not covered |
|---|---|
| All first-party Python and TypeScript source under `backend/`, `frontend/`, `notebooks/` | The datasets in §2 — each carries its own license from its original publisher |
| Configuration, migrations, Dockerfiles, and documentation | The pretrained models in §3 — governed by their own licenses and provider terms |
| Prompt text, schemas, and evaluation harness code | Live job postings retrieved at runtime, which remain the property of their publishers |

---

## 2. Dataset Licenses

| Dataset | Source | License | Notes |
|---|---|---|---|
| **ESCO v1.2.1** (English classification) | European Commission — [ESCO portal](https://esco.ec.europa.eu/) | **CC BY 4.0** (European Union open data) | Free to use, share, and adapt with attribution. Attribution text in §5 |
| **Resume Data (PDF)** | Kaggle — `hadikp/resume-data-pdf` | See the dataset's Kaggle listing | 8,905 single-page image-only resume PDFs. Used for development and evaluation only. **Not redistributed** in this repository |
| **Candidate Job Role Dataset** | Kaggle | See the dataset's Kaggle listing | Query side of the ranking experiments. **Not redistributed** |
| **LinkedIn Job Postings Dataset** | Kaggle | See the dataset's Kaggle listing | Offline document pool for ranking experiments. **Not redistributed** |
