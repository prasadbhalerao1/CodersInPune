# Single sign-on (SSO / SAML / OIDC)

Relay never handles passwords or SAML assertions. WorkOS AuthKit establishes identity,
and Relay verifies the resulting access token on every API request. Enterprise SSO is
therefore configured in WorkOS, and Relay needs no code changes.

## How identity and access fit together

1. **Identity.** WorkOS signs the user in, through password, magic link, social login, or the organisation's SAML/OIDC identity provider.
2. **Membership.** Relay grants nothing on sign-in. Access to a workspace comes only from an *active* Relay membership, created by accepting an invitation sent to a verified email.
3. **Role.** The role is set in Relay (Settings → Members) and checked by the permission registry.

Removing someone at the identity provider stops new sign-ins. Removing their Relay
membership revokes access at the next request, because nothing is cached.

## Requirements

- A WorkOS **production** environment with AuthKit enabled. This is already needed for any deployment ([../deployment.md](../deployment.md)).
- The customer's identity provider, such as Okta, Microsoft Entra ID, Google Workspace or OneLogin, and an admin there who can create a SAML or OIDC application.
- A verified domain for the organisation in WorkOS, so its users are routed to SSO.

## Setup

1. In the WorkOS dashboard, open **Organizations** and create an organisation for the customer. Add their email domain and verify it.
2. Under the organisation, go to **SSO** and either:
   - add a connection for their identity provider and send the customer the **Admin Portal** link, so their IT admin configures it with WorkOS's step-by-step guide; or
   - enter the IdP metadata yourself.
3. Under **Authentication**, enable SSO for AuthKit. Optionally require SSO for the verified domain, so password sign-in is refused for those users.
4. Test it: sign in at `https://<web>/sign-in` with an address on that domain. You should be sent to the identity provider and back to Relay.
5. In Relay, invite the organisation's people to the workspace by their SSO email address. Their memberships activate when they accept.

No Relay environment variables change. The API keeps verifying the same issuer and JWKS.

## Not supported yet

- **SCIM / directory sync to roles.** Relay doesn't create memberships or roles from identity-provider groups. People are invited in Relay, and deprovisioning still needs the membership removed in Relay (or the identity-provider block, which stops sign-in).
- **Just-in-time workspace membership by domain.** It's deliberate that every membership is an explicit invitation.
