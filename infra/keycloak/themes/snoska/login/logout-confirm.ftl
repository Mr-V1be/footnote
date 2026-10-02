<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
  <#if section = "header">
    ${msg("logoutConfirmTitle")}
  <#elseif section = "form">
    <p class="auth__lead">${msg("logoutConfirmHeader")}</p>
    <form class="form" action="${url.logoutConfirmAction}" method="post" onsubmit="confirmLogout.disabled = true; return true;">
      <input type="hidden" name="session_code" value="${logoutConfirm.code}">
      <button class="button button--primary button--block button--large" name="confirmLogout" id="kc-logout" type="submit">${msg("doLogout")}</button>
      <#if !logoutConfirm.skipLink && (client.baseUrl)?has_content>
        <a class="button button--secondary button--block" href="${client.baseUrl}">${msg("backToApplication")}</a>
      </#if>
    </form>
  </#if>
</@layout.registrationLayout>
