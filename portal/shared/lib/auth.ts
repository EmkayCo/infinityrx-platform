import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { API_URLS } from "./constants";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  mfa_required: boolean;
  mfa_challenge_token?: string;
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
    tenant_id: string;
    permissions: string[];
    mfa_enrolled: boolean;
  };
}

interface MfaVerifyResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
    tenant_id: string;
    permissions: string[];
    mfa_enrolled: boolean;
  };
}

// DEV-ONLY MOCK AUTH BYPASS — hard-refuses in production builds.
// Server-side guard: NODE_ENV !== "production" AND DEV_AUTH_BYPASS === "true".
// NEXT_PUBLIC_DEV_AUTH_BYPASS only controls the login UI button visibility.

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Credentials({
      id: "dev-bypass",
      name: "Dev Bypass (LOCAL ONLY)",
      credentials: {},
      async authorize() {
        if (process.env.NODE_ENV === "production") return null;
        if (process.env.DEV_AUTH_BYPASS !== "true") return null;
        const now = Math.floor(Date.now() / 1000);
        return {
          id: "dev-admin-00000000-0000-0000-0000-000000000001",
          email: "dev@infinityrx.local",
          name: "Dev Admin",
          role: "platform_admin",
          tenant_id: "00000000-0000-0000-0000-000000000001",
          permissions: ["*"],
          mfa_enrolled: true,
          access_token: "dev-bypass-token",
          refresh_token: "dev-bypass-refresh",
          expires_at: now + 60 * 60 * 8,
        };
      },
    }),
    Credentials({
      id: "b10-test",
      name: "B10 Test Bypass (TEST-MODE ONLY)",
      credentials: {
        token: { label: "Token", type: "text" },
      },
      async authorize(creds) {
        // Wave B10 W4.6: next start runtime probe bypass.
        // BOTH env vars must be set AND token must match exactly via
        // constant-time comparison. Hard-refuses if either is missing.
        // 32-byte random token lives in .env.local (gitignored).
        // security.md compliance: constant-time compare on secret.
        if (process.env.B10_TEST_MODE !== "true") return null;
        const expected = process.env.B10_TEST_TOKEN;
        if (!expected || !creds?.token) return null;
        const a = Buffer.from(String(creds.token));
        const b = Buffer.from(expected);
        if (a.length !== b.length) return null;
        let diff = 0;
        for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
        if (diff !== 0) return null;
        const now = Math.floor(Date.now() / 1000);
        return {
          id: "b10-test-admin-00000000-0000-0000-0000-000000000001",
          email: "b10-test@infinityrx.local",
          name: "B10 Test Admin",
          role: "platform_admin",
          tenant_id: "00000000-0000-0000-0000-000000000001",
          permissions: ["*"],
          mfa_enrolled: true,
          access_token: "b10-test-token",
          refresh_token: "b10-test-refresh",
          expires_at: now + 60 * 60, // 1 hour — test runs are short
        };
      },
    }),
    Credentials({
      id: "credentials",
      name: "Email & Password",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          return null;
        }

        try {
          // Backend mounts auth routes under /api/v1 (see
          // modules/core-platform/src/auth/api/__init__.py:13). Without
          // the prefix this 404s against the real app — it only worked
          // previously because auth was never live in prod.
          const response = await fetch(`${API_URLS.corePlatform}/api/v1/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: credentials.email,
              password: credentials.password,
            }),
          });

          if (!response.ok) {
            return null;
          }

          const data = (await response.json()) as LoginResponse;

          if (data.mfa_required) {
            // Return partial user to trigger MFA flow
            return {
              id: "mfa_required",
              email: String(credentials.email),
              mfa_required: true,
              mfa_challenge_token: data.mfa_challenge_token,
            };
          }

          return {
            id: data.user.id,
            email: data.user.email,
            name: data.user.name,
            role: data.user.role,
            tenant_id: data.user.tenant_id,
            permissions: data.user.permissions,
            mfa_enrolled: data.user.mfa_enrolled,
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            expires_at: Math.floor(Date.now() / 1000) + data.expires_in,
          };
        } catch {
          return null;
        }
      },
    }),
    Credentials({
      id: "mfa",
      name: "MFA Verification",
      credentials: {
        challenge_token: { label: "Challenge Token", type: "text" },
        code: { label: "MFA Code", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.challenge_token || !credentials?.code) {
          return null;
        }

        try {
          const response = await fetch(
            `${API_URLS.corePlatform}/api/v1/auth/mfa/verify`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                challenge_token: credentials.challenge_token,
                code: credentials.code,
              }),
            }
          );

          if (!response.ok) {
            return null;
          }

          const data = (await response.json()) as MfaVerifyResponse;

          return {
            id: data.user.id,
            email: data.user.email,
            name: data.user.name,
            role: data.user.role,
            tenant_id: data.user.tenant_id,
            permissions: data.user.permissions,
            mfa_enrolled: data.user.mfa_enrolled,
            access_token: data.access_token,
            refresh_token: data.refresh_token,
            expires_at: Math.floor(Date.now() / 1000) + data.expires_in,
          };
        } catch {
          return null;
        }
      },
    }),
  ],
  session: {
    strategy: "jwt",
    maxAge: 15 * 60, // 15 minutes idle timeout
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        const u = user as Record<string, unknown>;
        token.id = u["id"] as string;
        token.role = u["role"] as string;
        token.tenant_id = u["tenant_id"] as string;
        token.permissions = u["permissions"] as string[];
        token.mfa_enrolled = u["mfa_enrolled"] as boolean;
        token.access_token = u["access_token"] as string;
        token.refresh_token = u["refresh_token"] as string;
        token.expires_at = u["expires_at"] as number;
        token.mfa_required = u["mfa_required"] as boolean | undefined;
        token.mfa_challenge_token = u["mfa_challenge_token"] as string | undefined;
      }

      // Refresh token if expiring within 60 seconds
      const now = Math.floor(Date.now() / 1000);
      const expiresAt = token.expires_at as number | undefined;
      if (expiresAt && expiresAt - now < 60 && token.refresh_token) {
        try {
          const response = await fetch(
            `${API_URLS.corePlatform}/api/v1/auth/token/refresh`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ refresh_token: token.refresh_token }),
            }
          );
          if (response.ok) {
            const refreshed = (await response.json()) as {
              access_token: string;
              expires_in: number;
            };
            token.access_token = refreshed.access_token;
            token.expires_at = now + refreshed.expires_in;
          } else {
            token.error = "RefreshAccessTokenError";
          }
        } catch {
          token.error = "RefreshAccessTokenError";
        }
      }

      return token;
    },
    async session({ session, token }) {
      const s = session as typeof session & {
        user: Record<string, unknown>;
        access_token?: string;
        error?: string;
        mfa_required?: boolean;
        mfa_challenge_token?: string;
      };
      s.user.id = token.id as string;
      s.user.role = token.role as string;
      s.user.tenant_id = token.tenant_id as string;
      s.user.permissions = token.permissions as string[];
      s.user.mfa_enrolled = token.mfa_enrolled as boolean;
      s.access_token = token.access_token as string;
      s.error = token.error as string | undefined;
      s.mfa_required = token.mfa_required as boolean | undefined;
      s.mfa_challenge_token = token.mfa_challenge_token as string | undefined;
      return s;
    },
  },
});

export type AuthSession = Awaited<ReturnType<typeof auth>>;
