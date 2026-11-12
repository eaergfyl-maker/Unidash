// Shared Tailwind theme, taken from the SyncFlow pitch deck.
// Load right after the Tailwind CDN script on every page.
tailwind.config = {
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#0a1f4f", 2: "#102f73", deep: "#06153a" },
        royal: "#0049ad",
        sky: "#7ed6ff",
        cream: "#fbf8f2",
        mist: "#e6ecf7",
        ember: "#ff8a4c",
        mint: "#5ee6a8",
      },
      fontFamily: {
        display: ['"Archivo Black"', "Poppins", "system-ui", "sans-serif"],
        sans: ["Poppins", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
      },
    },
  },
};
