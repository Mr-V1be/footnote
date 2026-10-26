// Choosing a language on the sign-in pages also chooses it for the app: the
// app keeps the visitor's choice in the same cookie and opens in it after
// sign-in. Cookies are shared with the app when both are served from one
// host, as on the stand and under a path of the product's name.
(function () {
  var YEAR = 60 * 60 * 24 * 365;
  document.addEventListener("click", function (event) {
    var link =
      event.target.closest && event.target.closest("[data-footnote-locale]");
    if (!link) return;
    document.cookie =
      "footnote_locale=" +
      link.getAttribute("data-footnote-locale") +
      "; path=/; max-age=" +
      YEAR +
      "; samesite=lax";
  });
})();
