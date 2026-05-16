import "server-only";
import NextAuth, { type NextAuthConfig } from "next-auth";
import Credentials from "next-auth/providers/credentials";
// Plan B's verify oracle — called at JWT creation time.
// If verifyAccessToken throws AuthError, jwt callback returns null
// and next-auth clears the session cookie.
import { verifyAccessToken } from "@infinityrx/auth";

export const authConfig: NextAuthConfig = {
  providers: [
    Credentials({
      /**
       * The InfinityRx portal does not use credentials directly here —
       * authentication is delegated to the Python auth service, which
       * returns a signed access_token + refresh_token pair.
       * The `authorize` callback receives those tokens from the login form.
       */
      async authorize(credentials) {
        if (!credentials?.access_token) return null;
        // Verify via Plan B's verify chain: checks signature, expiry, and
        // Redis revocation list. Throws AuthError on any failure.
        const payload = await verifyAccessToken(credentials.access_token as string);
        return {
          id: payload.sub,
          access_token: credentials.access_token as string,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // On initial sign-in, user is populated by authorize().
      if (user?.access_token) {
        // Verify (again) and extract claims into session token.
        // This ensures the JWT stored in the encrypted cookie was produced
        // by a token that passed Plan B's verify chain.
        const payload = await verifyAccessToken(user.access_token as string);
        token.sub = payload.sub;
        token.tid = payload.tid as string;
        token.roles = payload.roles as string[];
        token.mfaEnrolled = (payload.mfa_enrolled ?? false) as boolean;
      }
      // On subsequent refreshes, the claims are already in the token.
      // Per-request revocation checking is deferred to a future wave;
      // revocation is enforced at login + token-refresh boundaries only.
      return token;
    },
    async session({ session, token }) {
      // Propagate claims from JWT into session.user for getSessionUser().
      session.user = {
        ...session.user,
        sub: token.sub as string,
        tid: token.tid as string,
        roles: token.roles as string[],
        mfaEnrolled: token.mfaEnrolled as boolean,
      };
      return session;
    },
  },
  session: { strategy: "jwt" },
};

export const { auth, handlers, signIn, signOut } = NextAuth(authConfig);
