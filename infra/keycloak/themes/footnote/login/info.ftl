<#import "template.ftl" as layout>
<#import "footnote.ftl" as ui>
<@layout.registrationLayout displayMessage=false; section>
  <#if section = "header">
    <#if messageHeader??>${kcSanitize(msg("${messageHeader}"))?no_esc}<#else>${message.summary}</#if>
  <#elseif section = "form">
    <p class="auth__lead" id="kc-info-message">${message.summary}<#if requiredActions??><#list requiredActions>: <#items as action>${kcSanitize(msg("requiredAction.${action}"))?no_esc}<#sep>, </#items></#list></#if></p>
    <#if !skipLink??>
      <#if pageRedirectUri?has_content>
        <a class="button button--primary button--block" href="${pageRedirectUri}">${msg("backToApplication")}</a>
      <#elseif actionUri?has_content>
        <a class="button button--primary button--block" href="${actionUri}">${msg("proceedWithAction")}</a>
      <#elseif (client.baseUrl)?has_content>
        <a class="button button--secondary button--block" href="${client.baseUrl}">${msg("backToApplication")}</a>
      </#if>
    </#if>
  </#if>
</@layout.registrationLayout>
