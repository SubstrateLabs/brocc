# Adding OAuth Providers

## Lifecycle
- OAuth token data is stored in redis with a short (1hr) TTL.
- The CLI initiates the oauth flow, and stores tokens locally (retrieved from redis within the TTL)

## Adding a new provider
- Update `lib/oauth/oauth-providers.ts` with the new provider slug
- Add a provider to `lib/oauth/providers` following `lib/oauth/provider-interface.ts`
- Update `lib/oauth/handle-callback.ts` with the validate function
- Update `api/auth/url/[provider]/route.ts` with the oauth url function

## Notes
- We don't handle "incremental auth" – this adds complexity, as it would require storing scopes, and requesting old scopes along with new scopes. Only some providers (e.g. Google) support it. Prioritizing simplicity of adding new providers.