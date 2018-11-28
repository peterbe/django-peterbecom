// Auth0 / OIDC
export const OIDC_CLIENT_ID =
  process.env.REACT_APP_OIDC_CLIENT_ID || 'AOIXT00k5GdT8LdLNGl84wGrpsloQvAf';
export const OIDC_DOMAIN =
  process.env.REACT_APP_OIDC_DOMAIN || 'peterbecom.auth0.com';
const defaultCallbackUrl = `${window.location.protocol}//${
  window.location.host
}/`;
export const OIDC_CALLBACK_URL =
  process.env.REACT_APP_OIDC_CALLBACK_URL || defaultCallbackUrl;
export const OIDC_AUDIENCE =
  process.env.REACT_APP_OIDC_AUDIENCE || `https://${OIDC_DOMAIN}/userinfo`;

export const BASE_URL =
  process.env.REACT_APP_BASE_URL || 'https://www.peterbe.com';
