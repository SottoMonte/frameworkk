package presentation.api

default can_access = false

# Accesso API pubbliche senza autenticazione
can_access {
  input.path == "/api/public/news"
  input.method == "GET"
}

# Accesso API con autenticazione
can_access {
  input.path == "/api/user/profile"
  input.method == "GET"
  input.user.id != ""
}

# Solo admin può fare DELETE su API critiche
can_access {
  input.path == "/api/users"
  input.method == "DELETE"
  input.user.roles[_] == "admin"
}