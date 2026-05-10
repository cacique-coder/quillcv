# Stripe Tax — operational setup

QuillCV checkout sessions are created with `automatic_tax={"enabled": True}`
in `app/web/routes/payments.py`. That parameter is a no-op until Stripe Tax
is enabled in the dashboard *and* there is at least one tax registration on
file. Until then Stripe will collect $0 tax — checkout still works, but
nothing is calculated.

## Why this matters

QuillCV is a **digital service** (cloud-delivered software). For digital
services, most jurisdictions require the seller to charge consumption tax
(GST / VAT / sales tax) based on the *customer's* location, not the
seller's. Australia (our home jurisdiction) treats us as required to
register for GST on B2C digital sales once we cross the AUD $75k threshold.
Other countries have similar low thresholds.

## Order of registrations (do as revenue from each market crosses threshold)

1. **Australia (GST)** — register first. We're AU-based. ~10% on B2C sales
   to AU consumers. ABN-holding business customers can self-assess (Stripe
   Tax handles the reverse-charge automatically when a valid ABN is
   provided at checkout).
2. **United States** — economic-nexus thresholds vary by state ($100k or
   200 transactions in most states). Stripe Tax tracks per-state thresholds
   and surfaces a warning when one is crossed; register state-by-state as
   warnings appear.
3. **United Kingdom (VAT)** — 20% standard rate, no threshold for non-UK
   sellers of digital services.
4. **EU (OSS)** — single One-Stop-Shop registration covers all 27 member
   states. ~17–27% depending on customer country.

## Dashboard steps

1. Stripe Dashboard → **Tax** → **Get started**.
2. Add an **origin address** (our AU office) and confirm the product type
   is **Digital service / SaaS**. Stripe will assign the right product tax
   code (`txcd_10000000` — General SaaS).
3. **Registrations** → add Australia first. Provide our ABN.
4. (Later, as markets grow) add US states / UK / EU as above.

## Things to test after enabling

- Create a test-mode checkout from an **AU postcode**. The order summary
  should show a **GST** line item at 10% of the subtotal.
- Create a test-mode checkout from a **US ZIP** before US registration is
  added. No tax line should appear (Stripe correctly omits tax for
  jurisdictions we're not registered in).
- Create a test-mode checkout from the **UK / a EU country** before those
  registrations exist — same: no tax line, just the base price.
- Verify the hosted invoice (enabled via `invoice_creation`) shows the
  tax breakdown when present, and falls back to a clean receipt when
  there's no tax.

## References

- Stripe Tax overview: https://docs.stripe.com/tax
- Tax behavior for prices: https://docs.stripe.com/tax/products-prices-tax-codes-tax-behavior
- Australia-specific guidance: https://docs.stripe.com/tax/supported-countries/asia-pacific/australia

> Not legal advice. Confirm thresholds and obligations with our accountant
> before each new registration.
