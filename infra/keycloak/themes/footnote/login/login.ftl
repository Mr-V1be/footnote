<#import "template.ftl" as layout>
<#import "footnote.ftl" as ui>
<#import "passkeys.ftl" as passkeys>
<#-- Sign-in on one page, used when the flow asks for e-mail and password together. -->
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password'); section>
  <#if section = "header">
    ${msg("footnoteSignInTitle")}
  <#elseif section = "form">
    <#if realm.password>
      <form id="kc-form-login" class="form" action="${url.loginAction}" method="post" onsubmit="login.disabled = true; return true;">
        <#if !usernameHidden??>
          <@ui.emailField value=(login.username!'') errorFields=["username", "password"]/>
          <@ui.passwordField errorFields=[]/>
        <#else>
          <@ui.passwordField errorFields=["username", "password"] autofocus=true/>
        </#if>
        <div class="form__row">
          <#if realm.rememberMe && !usernameHidden??>
            <label class="checkbox">
              <input class="checkbox__input" id="rememberMe" name="rememberMe" type="checkbox" <#if login.rememberMe??>checked</#if>>
              <span>${msg("rememberMe")}</span>
            </label>
          </#if>
          <#if realm.resetPasswordAllowed>
            <a class="form__link" href="${url.loginResetCredentialsUrl}">${msg("doForgotPassword")}</a>
          </#if>
        </div>
        <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>>
        <button class="button button--primary button--block button--large" name="login" id="kc-login" type="submit">${msg("doLogIn")}</button>
      </form>
    </#if>
    <@passkeys.conditionalUIData />
  </#if>
</@layout.registrationLayout>
