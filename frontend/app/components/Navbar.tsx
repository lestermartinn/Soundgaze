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
  const userImage = session?.user?.image;

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
    <nav className="relative z-20 flex items-center justify-between px-6 h-14 bg-spotify-black shrink-0">

      {/* ── Left: Wordmark + Live Data ── */}
      <div className="flex items-center gap-3">
        <span className="w-3 h-8 bg-spotify-green" />
        <span className="font-black text-xl uppercase tracking-widest text-white">
          Soundgaze
        </span>
        <div className="hidden md:flex items-center gap-2 ml-2">
          <span className="relative flex h-2 w-2 shrink-0">
            <span
              className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75"
              style={{ backgroundColor: "#1DB954" }}
            />
            <span
              className="relative inline-flex rounded-full h-2 w-2"
              style={{ backgroundColor: "#1DB954" }}
            />
          </span>
          <span className="font-black text-[10px] uppercase tracking-widest" style={{ color: "#1DB954" }}>
            Live Data
          </span>
        </div>
      </div>

      {/* ── Right: Auth status ── */}
      <div className="flex items-center gap-4">
        {isLoading ? (
          <span className="font-mono text-xs text-white/40 uppercase tracking-widest animate-pulse">
            Connecting...
          </span>
        ) : isAuthenticated ? (
          <>
            {/* Profile avatar */}
            {userImage ? (
              <img
                src={userImage}
                alt={userName ?? "Profile"}
                title={userName ?? undefined}
                className="w-8 h-8 rounded-full border-2 object-cover"
                style={{ borderColor: "#1DB954" }}
              />
            ) : (
              <div
                className="w-8 h-8 rounded-full border-2 flex items-center justify-center"
                style={{ borderColor: "#1DB954", backgroundColor: "#1DB954" }}
                title={userName ?? undefined}
              >
                <span className="font-black text-[10px] text-black uppercase">
                  {userName?.[0] ?? "?"}
                </span>
              </div>
            )}
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
                         border-2 transition-all hover:-translate-y-px active:translate-y-0"
              style={{
                borderColor: "#1DB954",
                color: "#1DB954",
                boxShadow: "2px 2px 0px 0px #1DB954",
              }}
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
