# Local browser acceptance — 2026-09-17 UTC

Agent-operated synthetic self-test, using Playwright CLI's isolated Chromium
session `caseflow-r2-gates`. No human participant or time-saving claim.
Application candidate: `38fab84`; local realm import fix: `31e1a57`.

## Observed journey

1. Admin signed in through Keycloak, created/published **Browser R2 approvals**,
   uploaded/validated/published **Browser R2 purchase document**, and indexed and
   published **Browser R2 lamp policy**. Existing synthetic memberships were used.
2. Requester created **Browser R2 desk lamp purchase**, chose those versions,
   assigned manager then finance, and uploaded `fixtures/quotes/browser-upload.txt`
   through the HTML file input. Source preview preserved page/character details.
3. Extraction succeeded. Saved total remained USD 0.00 before acceptance;
   explicitly selecting Vendor, Currency and Line items saved the exact supplier,
   two lamps at USD 35.00, and the server-calculated USD 70.00 total.
4. Refreshed published policies and generated a cited review. It identified the
   actually absent cost center and justification, and cited the lamp policy.
   Requester supplied both manually and submitted the case.
5. Finance had no approval control before manager approval. Manager approved;
   finance then had an enabled approval control and approved. The case became
   APPROVED; the separately queued document reached SUCCEEDED.
6. Clicked **Download Word document**, captured the real browser download and
   saved `output/playwright/r2-approved-purchase.docx`. Word content contained the
   expected vendor, lamps, USD 70.00, cost center, justification and manager →
   finance order, with no unresolved placeholders. API readback matched its
   36,989 bytes and SHA-256. Two approval audit records and suggestion acceptance
   were present. Readback and raw synthetic model outputs are in `readback.json`.

The two selected model calls cost USD 0.001709 in `calls.json`; they share the
existing USD 10 lifetime ceiling. Other evaluation jobs ran concurrently.

## Focused usability checks

- Zero quantity prevented saving and showed the alert **Quantity must be positive**.
- At 390 × 844, document scroll width was 390 pixels: no horizontal page overflow.
- Keyboard activation of **Skip to content** focused `#workspace`.
- Tab from Cost center moved to the labeled business-justification field;
  keyboard-entered values saved and appeared in the downloaded document.
- Previous AI results were visibly stale after changes; their acceptance button
  and field checkboxes were disabled.
- A fast automation sequence attempted upload before the assignment
  save refreshed the case version. Server returned 409 and UI showed **The resource
  changed. Reload it before trying again.** Retrying after refresh succeeded.
  No stale overwrite occurred. This observed conflict is retained, not hidden.
- Desktop approval/download and mobile assistant screenshots were visually read.

These are focused accessibility checks, not a complete WCAG or screen-reader
audit. File input/download events were automated; Windows OS dialogs were not
clicked. Manual fallback under simulated assistant 503 was separately verified in
`../../2026-09-15-r2/browser-file-and-fallback.json`. This journey did not simulate
a provider outage or test cloud deployment. Existing memberships were not recreated.

## Reproduce readback

With local services running and the same synthetic database:

```powershell
node tests/e2e/browser-journey-readback.mjs --tenant 69461d55-4af7-46b4-aac9-946d0807eac9 --case 6b775869-9ff2-4a8a-8959-a9fa2b4f7578 --document output/playwright/r2-approved-purchase.docx --output NEW_READBACK.json
```

This command checks recorded state and downloaded bytes. It does not replay the
browser steps. Repeating the browser journey requires new named synthetic inputs;
keep old records and evidence unchanged.
