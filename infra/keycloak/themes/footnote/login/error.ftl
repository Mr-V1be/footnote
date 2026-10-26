<#import "template.ftl" as layout>
<#import "footnote.ftl" as ui>
<@layout.registrationLayout displayMessage=false; section>
  <#if section = "header">
    ${msg("errorTitle")}
  <#elseif section = "form">
    <@ui.alert type="error" text=message.summary/>
    <#if traceId??>
      <p class="auth__note" id="traceId">${msg("footnoteTrace", traceId)}</p>
    </#if>
    <#if !skipLink?? && client?? && client.baseUrl?has_content>
      <a class="button button--secondary button--block" id="backToApplication" href="${client.baseUrl}">${msg("backToApplication")}</a>
    </#if>
  </#if>
</@layout.registrationLayout>
