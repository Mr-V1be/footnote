// Shows or hides the password; the button reports its state to assistive tech.
document.querySelectorAll("[data-password-toggle]").forEach(function (button) {
  var input = document.getElementById(button.getAttribute("aria-controls"));
  if (!input) return;
  button.addEventListener("click", function () {
    var shown = input.type === "text";
    input.type = shown ? "password" : "text";
    button.setAttribute("aria-pressed", String(!shown));
    button.setAttribute(
      "aria-label",
      shown ? button.dataset.labelShow : button.dataset.labelHide,
    );
  });
});
