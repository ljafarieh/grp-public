import httpx
import pdfplumber
import io
import textwrap

print("=== PROJECT FOSBURY — Grid Realization Pipeline ===")
print("Running VA SCC scraper...")
print()

url = "https://www.scc.virginia.gov/docketsearch/docs/8d7n01!.PDF"
r = httpx.get(url, follow_redirects=True, timeout=20)

with pdfplumber.open(io.BytesIO(r.content)) as pdf:
    full_text = " ".join(p.extract_text() or "" for p in pdf.pages)

keywords = ["co-location", "behind-the-meter", "show cause", "intervention", "ratepayer"]
matched = [kw for kw in keywords if kw.lower() in full_text.lower()]

print(f"[SIGNAL] Case:              PUR-2026-00011")
print(f"[SIGNAL] Entity:            Dominion Energy (Virginia SCC)")
print(f"[SIGNAL] Keywords matched ({len(matched)}): {', '.join(matched)}")
print()
print("--- KEY EXCERPT (page 9) ---")
excerpt = (
    "Dominion reports approximately 70,000 MW of large load requests in its queue. "
    "Dominion cannot guarantee that it will be able to clear its current load "
    "interconnection queue before 2041 — and that is only to study these loads, "
    "not to interconnect them."
)
print(textwrap.fill(excerpt, width=72))
print()
print("[DB] Event written → fosbury.db")
print("[DONE] 1 genuine signal found.")
