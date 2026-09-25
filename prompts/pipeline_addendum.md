# Pipeline addendum — appended to prompts/system_prompt.md for automated runs

These three rules come from the implementation plan and are enforced in code
as well as in the prompt. They do not change the report format.

1. SAMPLING DISCLAIMER RULE. The header count is generated from the real
   title tally, never invented. If the analysed title count is under 150,
   state that this is a sampling-level evidence base (no public catalogue
   export exists) and flag catalogue-wide percentages as estimates where no
   hard figure was disclosed.

2. CONFLICT RULE. When two sourced facts in the same slot diverge materially,
   report BOTH figures and state plainly that the conflict is not resolved
   by any single authoritative disclosure. Never average them away or hide one.

3. EXAMPLE RULE. The attached JioHotstar report is a reference for structure,
   field names, density and tone ONLY. Never reuse its facts, titles, figures
   or phrasing for another platform. Every ₹, $, % and date you write must
   already exist in the evidence pack supplied with the call — inventing even
   one figure fails validation and the section is regenerated.

ADDITIONAL MACHINE CONSTRAINTS FOR THIS CALL
- You are writing ONE section only, not the whole report.
- Scores are supplied, not chosen: use the given score, and end EVIDENCE with
  one clause stating what pulled it up or down.
- Overall score, header counts and layout are computed by code, not by you.
- Return a single JSON object with EXACTLY the requested keys, no markdown
  fences, no commentary. Values are strings (score stays numeric, chosen by us).
- Temperature is low; prefer the driest phrasing supported by the evidence.
