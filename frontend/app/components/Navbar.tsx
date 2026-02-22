"use client";

import { useState } from "react";
import { useSession, signIn, signOut } from "next-auth/react";

export default function Navbar() {
  const { data: session, status } = useSession();
  const isLoading = status === "loading";
  const isAuthenticated = status === "authenticated";
  const userName = session?.user?.name;
  const spotifyId = session?.spotifyId;
  const accessToken = session?.accessToken;
  const [copiedId, setCopiedId] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);

  function copySpotifyId() {
    if (!spotifyId) return;
    navigator.clipboard.writeText(spotifyId).then(() => {
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    });
  }

  function copyAccessToken() {
    if (!accessToken) return;
    navigator.clipboard.writeText(accessToken).then(() => {
      setCopiedToken(true);
      setTimeout(() => setCopiedToken(false), 2000);
    });
  }

  return (
    <nav className="relative z-20 flex items-center justify-between px-6 h-14 bg-spotify-black border-b-4 border-black shrink-0">

      {/* ── Left: Wordmark ── */}
      <div className="flex items-center gap-3">
        <span className="w-3 h-8 bg-spotify-green" />
        <span className="font-black text-xl uppercase tracking-widest text-white">
          Soundgaze
        </span>
      </div>

      {/* ── Right: Auth status ── */}
      <div className="flex items-center gap-4">
        {isLoading ? (
          <span className="font-mono text-xs text-white/40 uppercase tracking-widest animate-pulse">
            Connecting...
          </span>
        ) : isAuthenticated && userName ? (
          <>
            <span className="hidden sm:block font-mono font-bold text-xs tracking-widest text-white/60 uppercase">
              {userName}
            </span>
            {spotifyId && (
              <button
                onClick={copySpotifyId}
                title="Click to copy Spotify user ID"
                className="hidden sm:block font-mono text-xs text-white/30 hover:text-white/60
                           transition-colors border border-white/10 hover:border-white/30
                           px-2 py-1 leading-none"
              >
                {copiedId ? "✓ Copied" : `ID: ${spotifyId}`}
              </button>
            )}
            {accessToken && (
              <button
                onClick={copyAccessToken}
                title="Click to copy Spotify access token"
                className="hidden sm:block font-mono text-xs text-white/30 hover:text-white/60
                           transition-colors border border-white/10 hover:border-white/30
                           px-2 py-1 leading-none"
              >
                {copiedToken ? "✓ Token Copied" : "Copy Token"}
              </button>
            )}
            <button
              onClick={() => signOut({ callbackUrl: "http://127.0.0.1:3000" })}
              className="font-black text-xs uppercase tracking-widest px-4 py-2
                         border-2 border-white/30 text-white/60
                         hover:border-white hover:text-white transition-colors"
            >
              Disconnect
            </button>
          </>
        ) : (
          <button
            onClick={() => signIn("spotify")}
            className="font-black text-xs uppercase tracking-widest px-4 py-2
                       border-2 border-black
                       shadow-[3px_3px_0px_0px_#000]
                       hover:shadow-[5px_5px_0px_0px_#000] hover:-translate-y-px
                       active:shadow-none active:translate-y-0
                       transition-all"
            style={{ backgroundColor: "#1DB954", color: "#000" }}
          >
            Connect Spotify
          </button>
        )}
      </div>

    </nav>
  );
}
