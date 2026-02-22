import NextAuth, { DefaultSession } from "next-auth";
import { JWT } from "next-auth/jwt";

// Extend the built-in session/JWT types so TypeScript knows about accessToken
declare module "next-auth" {
  interface Session extends DefaultSession {
    accessToken?: string;
    spotifyId?: string;
    error?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    accessToken?: string;
    refreshToken?: string;
    accessTokenExpires?: number;
    spotifyId?: string;
    error?: string;
  }
}
