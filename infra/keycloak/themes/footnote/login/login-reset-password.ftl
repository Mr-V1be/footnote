<#import "template.ftl" as layout>
<#import "footnote.ftl" as ui>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username'); section>
  <#if section = "header">
    ${msg("emailForgotTitle")}
  <#elseif section = "form">
    <p class="auth__lead">${msg("emailInstruction")}</p>
    <form id="kc-reset-password-form" class="form" action="${url.loginAction}" method="post">
      <@ui.emailField value=(auth.attemptedUsername!'')/>
      <button class="button button--primary button--block button--large" type="submit">${msg("doSubmit")}</button>
      <a class="form__back" href="${url.loginUrl}"><@ui.icon name="arrow-left"/>${msg("backToLogin")}</a>
    </form>
  </#if>
</@layout.registrationLayout>
