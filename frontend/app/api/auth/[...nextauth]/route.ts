import NextAuth from "next-auth";
import SpotifyProvider from "next-auth/providers/spotify";

const SPOTIFY_SCOPES =
  "user-read-private user-read-email user-library-modify user-top-read streaming";

const handler = NextAuth({
  // Force plain (non-__Secure-prefixed) cookies for local HTTP dev on 127.0.0.1
  useSecureCookies: false,
  cookies: {
    sessionToken:      { name: "next-auth.session-token",         options: { httpOnly: true, sameSite: "lax", path: "/", secure: false } },
    callbackUrl:       { name: "next-auth.callback-url",          options: { httpOnly: true, sameSite: "lax", path: "/", secure: false } },
    csrfToken:         { name: "next-auth.csrf-token",            options: { httpOnly: true, sameSite: "lax", path: "/", secure: false } },
    pkceCodeVerifier:  { name: "next-auth.pkce.code_verifier",    options: { httpOnly: true, sameSite: "lax", path: "/", secure: false } },
    state:             { name: "next-auth.state",                 options: { httpOnly: true, sameSite: "lax", path: "/", secure: false } },
    nonce:             { name: "next-auth.nonce",                 options: { httpOnly: true, sameSite: "lax", path: "/", secure: false } },
  },
  providers: [
    SpotifyProvider({
      clientId: process.env.SPOTIFY_CLIENT_ID!,
      clientSecret: process.env.SPOTIFY_CLIENT_SECRET!,
      authorization: {
        params: { scope: SPOTIFY_SCOPES },
      },
      // Override userinfo to bypass openid-client's request — Spotify requires
      // the Bearer token in the Authorization header, not as a form body param.
      userinfo: {
        url: "https://api.spotify.com/v1/me",
        async request({ tokens }) {
          const res = await fetch("https://api.spotify.com/v1/me", {
            headers: { Authorization: `Bearer ${tokens.access_token}` },
          });
          if (!res.ok) {
            throw new Error(`Spotify /v1/me returned ${res.status}`);
          }
          return res.json();
        },
      },
    }),
  ],
  callbacks: {
    async jwt({ token, account, profile }) {
      if (account) {
        token.accessToken = account.access_token;
        token.refreshToken = account.refresh_token;
        token.accessTokenExpires = account.expires_at
          ? account.expires_at * 1000
          : 0;
      }
      if (profile) {
        token.spotifyId = (profile as { id?: string }).id;
      }
      if (Date.now() < (token.accessTokenExpires as number)) {
        return token;
      }
      return refreshAccessToken(token);
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string;
      session.spotifyId = token.spotifyId as string | undefined;
      session.error = token.error as string | undefined;
      return session;
    },
  },
});

async function refreshAccessToken(token: Record<string, unknown>) {
  try {
    const params = new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: token.refreshToken as string,
    });
    const response = await fetch("https://accounts.spotify.com/api/token", {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        Authorization:
          "Basic " +
          Buffer.from(
            `${process.env.SPOTIFY_CLIENT_ID}:${process.env.SPOTIFY_CLIENT_SECRET}`
          ).toString("base64"),
      },
      body: params,
    });
    const refreshed = await response.json();
    if (!response.ok) throw refreshed;
    return {
      ...token,
      accessToken: refreshed.access_token,
      refreshToken: refreshed.refresh_token ?? token.refreshToken,
      accessTokenExpires: Date.now() + refreshed.expires_in * 1000,
    };
  } catch (error) {
    console.error("Failed to refresh Spotify access token:", error);
    return { ...token, error: "RefreshAccessTokenError" };
  }
}

export { handler as GET, handler as POST };
