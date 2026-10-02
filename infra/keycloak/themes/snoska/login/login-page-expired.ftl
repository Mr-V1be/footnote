<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
  <#if section = "header">
    ${msg("pageExpiredTitle")}
  <#elseif section = "form">
    <p class="auth__lead">${msg("pageExpiredMsg1")}</p>
    <div class="form">
      <a class="button button--primary button--block button--large" id="loginRestartLink" href="${url.loginRestartFlowUrl}">${msg("snoskaRestartSignIn")}</a>
      <a class="button button--secondary button--block" id="loginContinueLink" href="${url.loginAction}">${msg("snoskaContinueSignIn")}</a>
    </div>
  </#if>
</@layout.registrationLayout>
