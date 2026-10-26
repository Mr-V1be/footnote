<#import "template.ftl" as layout>
<#import "footnote.ftl" as ui>
<#import "passkeys.ftl" as passkeys>
<#-- Step one of sign-in: the e-mail identifies the person and the organisation. -->
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username'); section>
  <#if section = "header">
    ${msg("footnoteSignInTitle")}
  <#elseif section = "form">
    <p class="auth__lead">${msg("footnoteSignInLead")}</p>
    <#if realm.password>
      <form id="kc-form-login" class="form" action="${url.loginAction}" method="post" onsubmit="login.disabled = true; return true;">
        <#if !usernameHidden??>
          <@ui.emailField value=(login.username!'')/>
        </#if>
        <#if realm.rememberMe && !usernameHidden??>
          <label class="checkbox">
            <input class="checkbox__input" id="rememberMe" name="rememberMe" type="checkbox" <#if login.rememberMe??>checked</#if>>
            <span>${msg("rememberMe")}</span>
          </label>
        </#if>
        <button class="button button--primary button--block button--large" name="login" id="kc-login" type="submit">${msg("doContinue")}</button>
      </form>
    </#if>
    <@passkeys.conditionalUIData />
  </#if>
</@layout.registrationLayout>
