# Regex portability audit (2026-10-22)

The initial v2 diff introduced the component matcher and a duplicate of the existing
ASCII request-token check in the publisher. The component matcher is removed; bind
uses literal character scanning, with no dynamic Regex construction. The bounded
token expression has a valid {1,64} quantifier and no unescaped literal brace.
The inherited request parser, event sanitizer and padded-base64 expressions were
checked as context and retain their existing semantics. No other new pattern site
was found in the initial v2 source diff. JVM compilation is not Android ICU evidence.

## Initial v2 additions containing regex construction

+        val components = if (key == null) Regex("\\{([^{}]+)}").findAll(source)
+        require(token.matches(Regex("[A-Za-z0-9._-]{1,64}"))) { "invalid_request_id" }

## Current relevant source sites

android/src/com/unciv/app/AndroidGame.kt:40:            require(encoded.length <= 43692 && encoded.matches(Regex("[A-Za-z0-9+/]*={0,2}")))
core/src/com/unciv/l10n/L10nRequest.kt:21:            require(token.matches(Regex("[A-Za-z0-9._-]{1,64}"))) { "invalid_request_id" }
core/src/com/unciv/l10n/L10nDump.kt:191:        require(token.matches(Regex("[A-Za-z0-9._-]{1,64}"))) { "invalid_request_id" }
core/src/com/unciv/l10n/L10nScreenHook.kt:359:    private fun safe(value: String) = value.replace(Regex("[^A-Za-z0-9._,:-]"), "_").take(512).ifBlank { "missing" }
