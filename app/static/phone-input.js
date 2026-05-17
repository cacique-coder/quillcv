// Initialise intl-tel-input on every <input data-intl-tel> and submit the
// canonical E.164 number to the server instead of whatever the user typed.
//
// The macro `phone_input()` in templates/macros/ui.html renders the visible
// input. The library replaces the visible input's name attribute with empty
// (so it's not submitted) and adds a hidden input alongside it whose value
// gets set to the E.164 number on every change.
//
// We listen on `htmx:afterSwap` too because the wizard partials swap content
// into the page without a full reload — those new inputs also need init.

(function () {
  "use strict";

  // Region codes used by QuillCV → ISO 3166-1 alpha-2 country codes
  // accepted by intl-tel-input. Most are identical; UK is the notable
  // exception (intl-tel-input uses "gb").
  var REGION_TO_ISO = {
    AU: "au", US: "us", UK: "gb", CA: "ca", NZ: "nz",
    DE: "de", FR: "fr", NL: "nl", IN: "in", BR: "br",
    AE: "ae", JP: "jp", CO: "co", VE: "ve", ES: "es",
    IT: "it", AR: "ar", MX: "mx",
  };

  function regionToIso(code) {
    if (!code) return null;
    return REGION_TO_ISO[code.toUpperCase()] || code.toLowerCase();
  }

  function initPhoneInput(input) {
    // Skip if already initialised (idempotent for HTMX re-runs).
    if (input.dataset.itiReady === "1") return;
    if (typeof window.intlTelInput !== "function") return;

    var initialCountry = regionToIso(input.dataset.region) || "au";

    var iti = window.intlTelInput(input, {
      initialCountry: initialCountry,
      // utils.js gives us formatting + libphonenumber-backed validation.
      utilsScript: "/static/vendor/intl-tel-input/js/utils.js",
      // Create a hidden input that takes over the original `name` attribute
      // so the form submits a canonical E.164 number (e.g. "+61400111222").
      // The visible input's name is cleared by the library.
      hiddenInput: function (telInputName) {
        return { phone: telInputName };
      },
      // Pretty-format the number as the user types.
      formatAsYouType: true,
      // Preferred countries shown at the top of the dropdown.
      countryOrder: ["au", "us", "gb", "ca", "nz"],
      separateDialCode: false,
      // Use national format in the visible input so users see "0400 111 222"
      // rather than "+61 400 111 222" when in their own country.
      nationalMode: true,
      // The hidden input we submit always gets the full E.164 number.
      // (Configured via the hiddenInput callback above.)
    });

    input.dataset.itiReady = "1";
    input._iti = iti;  // expose for debugging

    // Strip any existing flag span the legacy markup might have rendered
    // — the library now provides its own.
    var legacyFlag = input.parentNode && input.parentNode.querySelector(
      "[data-phone-flag='" + (input.dataset.legacyName || input.name) + "']"
    );
    if (legacyFlag) legacyFlag.remove();

    var legacyHint = input.parentNode && input.parentNode.querySelector(".phone-input-hint");
    if (legacyHint) legacyHint.remove();
  }

  function initAll(root) {
    var scope = root || document;
    scope.querySelectorAll("input[data-intl-tel]").forEach(initPhoneInput);
  }

  document.addEventListener("DOMContentLoaded", function () { initAll(); });

  // HTMX swaps content without a full reload — re-init any new phone inputs.
  document.addEventListener("htmx:afterSwap", function (evt) {
    initAll(evt.target || document);
  });
})();
