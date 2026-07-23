# Human Only

Agents must not do these without explicit user approval:

- Touch secrets, tokens, cookies, credentials, or private keys.
- Deploy, publish, submit, send emails/messages, spend money, or mutate production data.
- Take actions using the user's identity or accounts.
- Delete large amounts of data or history.

Project-specific additions:
- Never auto-purchase tickets or create orders on regmovies.com (createOrder
  endpoint exists — do not call it). Buying is Jacob's action.
- Do not shorten the poll interval below 10 min or the request gap below 2.5s
  (rate-limit courtesy).
