import Keycloak from "keycloak-js";

export const auth = new Keycloak({
  url: import.meta.env.VITE_OIDC_URL ?? "http://127.0.0.1:8180",
  realm: import.meta.env.VITE_OIDC_REALM ?? "caseflow",
  clientId: import.meta.env.VITE_OIDC_CLIENT ?? "caseflow-web",
});
let initialization: Promise<boolean> | undefined;
export function initializeAuth() {
  return (initialization ??= auth.init({
    onLoad: "check-sso",
    pkceMethod: "S256",
    checkLoginIframe: false,
  }));
}
