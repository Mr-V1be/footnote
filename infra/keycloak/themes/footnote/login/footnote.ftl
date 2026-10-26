<#-- Building blocks of the sign-in pages: icons, the wordmark and the specimen. -->

<#-- Tabler Icons (MIT), outline, stroke 1.75 — the icon set of the app. -->
<#assign iconPaths = {
  "alert-circle": ["M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0", "M12 8v4", "M12 16h.01"],
  "alert-triangle": ["M12 9v4", "M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0", "M12 16h.01"],
  "circle-check": ["M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0", "M9 12l2 2l4 -4"],
  "info-circle": ["M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0", "M12 9h.01", "M11 12h1v4h1"],
  "eye": ["M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0", "M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6"],
  "eye-off": ["M10.585 10.587a2 2 0 0 0 2.829 2.828", "M16.681 16.673a8.717 8.717 0 0 1 -4.681 1.327c-3.6 0 -6.6 -2 -9 -6c1.272 -2.12 2.712 -3.678 4.32 -4.674m2.86 -1.146a9.055 9.055 0 0 1 1.82 -.18c3.6 0 6.6 2 9 6c-.666 1.11 -1.379 2.067 -2.138 2.87", "M3 3l18 18"],
  "arrow-left": ["M5 12l14 0", "M5 12l6 6", "M5 12l6 -6"],
  "user-circle": ["M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0", "M9 10a3 3 0 1 0 6 0a3 3 0 1 0 -6 0", "M6.168 18.849a4 4 0 0 1 3.832 -2.849h4a4 4 0 0 1 3.834 2.855"]
}>

<#macro icon name class="icon">
  <svg class="${class}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><#list iconPaths[name] as d><path d="${d}"/></#list></svg>
</#macro>

<#-- The wordmark: the product name carries its own footnote marker, as in the app. -->
<#macro wordmark>
  <span class="wordmark" aria-label="${msg("footnoteName")}">
    <span class="wordmark__word" aria-hidden="true">${msg("footnoteName")}</span><sup class="wordmark__mark" aria-hidden="true">1</sup>
  </span>
</#macro>

<#--
  The interface languages, each by its code; the current one is marked.
  Choosing one also tells the app (js/language.js), so it opens in it.
-->
<#macro languages>
  <#if realm.internationalizationEnabled && locale?? && locale.supported?size gt 1>
    <nav class="languages" aria-label="${msg("footnoteLanguages")}">
      <#list locale.supported as language>
        <a class="languages__item" href="${language.url}" hreflang="${language.languageTag}" lang="${language.languageTag}"
           title="${language.label}" data-footnote-locale="${language.languageTag}"
           <#if language.languageTag == locale.currentLanguageTag>aria-current="true"</#if>>${language.languageTag?upper_case}</a>
      </#list>
    </nav>
  </#if>
</#macro>

<#macro demoMark>
  <span class="demo-mark">${msg("footnoteDemo")}</span>
</#macro>

<#macro alert type text>
  <#assign alertIcons = {"error": "alert-circle", "warning": "alert-triangle", "success": "circle-check", "info": "info-circle"}>
  <div class="alert alert--${type}" role="<#if type == 'error'>alert<#else>status</#if>">
    <@icon name=alertIcons[type]!"info-circle" class="alert__icon"/>
    <span class="alert__text">${kcSanitize(text)?no_esc}</span>
  </div>
</#macro>

<#-- A finding as the product shows it: a marked phrase, its marker and the footnote. -->
<#macro specimen>
  <figure class="specimen" aria-label="${msg("footnoteSpecimenLabel")}">
    <div class="specimen__sheet" aria-hidden="true" lang="ru">
      <p class="specimen__heading">${msg("footnoteSpecimenHeading")}</p>
      <p class="specimen__text">${msg("footnoteSpecimenBefore")} <mark class="specimen__mark">${msg("footnoteSpecimenMarked")}</mark>&#8288;<sup class="specimen__marker">1</sup> ${msg("footnoteSpecimenAfter")}</p>
      <span class="specimen__line"></span>
      <span class="specimen__line specimen__line--short"></span>
      <span class="specimen__line"></span>
      <span class="specimen__line specimen__line--mid"></span>
    </div>
    <figcaption class="specimen__note">
      <span class="specimen__note-head">
        <span class="specimen__note-marker" aria-hidden="true">1</span>
        <span class="specimen__severity">${msg("footnoteSpecimenSeverity")}</span>
      </span>
      <span class="specimen__finding">${msg("footnoteSpecimenFinding")}</span>
      <span class="specimen__quote" lang="ru">${msg("footnoteSpecimenQuote")}</span>
      <span class="specimen__citation">${msg("footnoteSpecimenCitation")}</span>
    </figcaption>
  </figure>
</#macro>

<#-- The first error among the given form fields, or "" when there is none. -->
<#function fieldError fields>
  <#list fields as field>
    <#if messagesPerField.existsError(field)><#return messagesPerField.get(field)></#if>
  </#list>
  <#return "">
</#function>

<#-- The e-mail field; `errorFields` are the fields whose error it shows. -->
<#macro emailField value="" errorFields=["username"] autofocus=true>
  <#local error = fieldError(errorFields)>
  <#local invalid = error?has_content>
  <div class="field">
    <label class="field__label" for="username">${msg("email")}</label>
    <input class="input" id="username" name="username" type="email" value="${value}"
           autocomplete="${(enableWebAuthnConditionalUI?has_content)?then('username webauthn', 'username')}"
           inputmode="email" spellcheck="false" dir="ltr" <#if autofocus>autofocus</#if>
           <#if invalid>aria-invalid="true" aria-describedby="input-error-username"</#if>>
    <#if invalid>
      <span class="field__error" id="input-error-username" aria-live="polite">${kcSanitize(error)?no_esc}</span>
    </#if>
  </div>
</#macro>

<#macro passwordField errorFields=["password"] autofocus=false>
  <#local error = fieldError(errorFields)>
  <#local invalid = error?has_content>
  <div class="field">
    <label class="field__label" for="password">${msg("password")}</label>
    <div class="input-group">
      <input class="input" id="password" name="password" type="password" autocomplete="current-password" dir="ltr"
             <#if autofocus>autofocus</#if>
             <#if invalid>aria-invalid="true" aria-describedby="input-error-password"</#if>>
      <button class="input-group__toggle" type="button" aria-controls="password" aria-pressed="false"
              aria-label="${msg('showPassword')}" data-password-toggle
              data-label-show="${msg('showPassword')}" data-label-hide="${msg('hidePassword')}">
        <@icon name="eye" class="icon icon--when-hidden"/>
        <@icon name="eye-off" class="icon icon--when-shown"/>
      </button>
    </div>
    <#if invalid>
      <span class="field__error" id="input-error-password" aria-live="polite">${kcSanitize(error)?no_esc}</span>
    </#if>
  </div>
  <script type="module" src="${url.resourcesPath}/js/password-toggle.js"></script>
</#macro>
