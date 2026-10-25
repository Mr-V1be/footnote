<#import "snoska.ftl" as ui>
<#import "footer.ftl" as loginFooter>
<#--
  Layout of every sign-in page. The form sits in the entry column; on wide
  screens a showcase column shows what the product does: a finding with its
  footnote, set in the app's own typography.
-->
<#macro registrationLayout bodyClass="" displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="${lang}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="robots" content="noindex, nofollow">
  <meta name="color-scheme" content="light dark">
  <title>${msg("snoskaPageTitle")}</title>
  <link rel="icon" href="${url.resourcesPath}/img/icon.svg" type="image/svg+xml">
  <#list properties.styles?split(' ') as style>
    <link href="${url.resourcesPath}/${style}" rel="stylesheet">
  </#list>
  <#list properties.scripts?split(' ') as script>
    <script src="${url.resourcesPath}/${script}"></script>
  </#list>
  <script type="importmap">
    { "imports": { "rfc4648": "${url.resourcesCommonPath}/vendor/rfc4648/rfc4648.js" } }
  </script>
  <#if scripts??>
    <#list scripts as script>
      <script src="${script}" type="text/javascript"></script>
    </#list>
  </#if>
  <script type="module">
    <#outputformat "JavaScript">
    import { startSessionPolling } from ${(url.resourcesPath + "/js/authChecker.js")?c};
    startSessionPolling(${url.ssoLoginInOtherTabsUrl?c});
    </#outputformat>
  </script>
  <#if authenticationSession??>
    <script type="module">
      <#outputformat "JavaScript">
      import { checkAuthSession } from ${(url.resourcesPath + "/js/authChecker.js")?c};
      checkAuthSession(${authenticationSession.authSessionIdHash?c});
      </#outputformat>
    </script>
  </#if>
</head>

<body class="${bodyClass}" data-page-id="login-${pageId}">
<div class="auth">
  <main class="auth__entry">
    <header class="auth__brand">
      <@ui.wordmark/>
      <@ui.demoMark/>
      <@ui.languages/>
    </header>

    <div class="auth__panel">
      <h1 class="auth__title"><#nested "header"></h1>

      <#if auth?has_content && auth.showUsername() && !auth.showResetCredentials()>
        <#nested "show-username">
        <div class="account" id="kc-username">
          <@ui.icon name="user-circle" class="account__icon"/>
          <span class="account__name" id="kc-attempted-username">${auth.attemptedUsername}</span>
          <a class="account__change" id="reset-login" href="${url.loginRestartFlowUrl}" aria-label="${msg("snoskaChangeAccountLabel")}">${msg("snoskaChangeAccount")}</a>
        </div>
      </#if>

      <#-- App-initiated actions do not repeat the warning about the pending action. -->
      <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
        <@ui.alert type=message.type text=message.summary/>
      </#if>

      <#nested "form">

      <#if auth?has_content && auth.showTryAnotherWayLink()>
        <form id="kc-select-try-another-way-form" action="${url.loginAction}" method="post" class="auth__aside">
          <input type="hidden" name="tryAnotherWay" value="on">
          <button type="submit" class="link-button" id="try-another-way">${msg("doTryAnotherWay")}</button>
        </form>
      </#if>

      <#if switchOrganizationEnabled?? && switchOrganizationEnabled>
        <form id="kc-switch-organization-form" action="${url.loginAction}" method="post" class="auth__aside">
          <input type="hidden" name="switchOrganization" value="true">
          <button type="submit" class="link-button" id="switch-organization">${msg("doSwitchOrganization")}</button>
        </form>
      </#if>

      <#nested "socialProviders">

      <#if displayInfo>
        <div class="auth__info" id="kc-info">
          <#nested "info">
        </div>
      </#if>
    </div>

    <@loginFooter.content/>
  </main>

  <aside class="auth__showcase">
    <div class="showcase">
      <p class="showcase__title">${msg("snoskaShowcaseTitle")}</p>
      <p class="showcase__lead">${msg("snoskaShowcaseLead")}</p>
      <@ui.specimen/>
    </div>
  </aside>
</div>
</body>
</html>
</#macro>
