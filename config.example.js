// Copy this file to config.js and fill in your own values.
//
// Both Supabase values are in the Supabase dashboard under Project Settings > API.
// Use the public key ("publishable", called "anon" on older projects). It is safe
// to ship to the browser because row-level security only lets a signed-in user
// see their own cards. Never put the "secret" or "service_role" key here.
window.BOARD_CONFIG = {
  supabaseUrl: "https://YOUR-PROJECT.supabase.co",
  supabaseKey: "PASTE_YOUR_PUBLISHABLE_KEY",

  // Shown at the top of the page and in the browser tab.
  title: "Board",
  subtitle: "",

  // Optional. Columns from left to right. The first is "not started" and the
  // last is "done". Each id is what gets stored on a card, so renaming a column
  // is safe but changing an id orphans the cards already in it (they fall back
  // to the first column).
  columns: [
    { id: "todo", name: "To do" },
    { id: "doing", name: "In progress" },
    { id: "review", name: "Review" },
    { id: "done", name: "Done" }
  ],

  // Optional. The card types offered when adding a card. The first seven each
  // get their own colour, in this order.
  types: ["task", "idea", "bug", "reading"]
};
