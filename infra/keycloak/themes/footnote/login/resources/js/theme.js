// Applies the colour theme chosen in the app (the same cookie as the app uses).
// Without a choice the page follows the system setting.
(function () {
  var match = document.cookie.match(
    /(?:^|;\s*)snoska_theme=(light|dark)(?:;|$)/,
  );
  if (match) document.documentElement.setAttribute("data-theme", match[1]);
})();
