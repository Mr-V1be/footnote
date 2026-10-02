<#import "template.ftl" as layout>
<#import "snoska.ftl" as ui>
<#-- Step two of sign-in: the account is shown above, the password is asked here. -->
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('password'); section>
  <#if section = "header">
    ${msg("snoskaSignInTitle")}
  <#elseif section = "form">
    <form id="kc-form-login" class="form" action="${url.loginAction}" method="post" onsubmit="login.disabled = true; return true;">
      <@ui.passwordField autofocus=true/>
      <#if realm.resetPasswordAllowed>
        <a class="form__link" href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a>
      </#if>
      <button class="button button--primary button--block button--large" name="login" id="kc-login" type="submit">${msg("doLogIn")}</button>
    </form>
  </#if>
</@layout.registrationLayout>
